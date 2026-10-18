# Code Review Package — dsh-bridge-resilience-20261017

## 1. Metadata & Artifact Hashes
- **Task ID**: `dsh-bridge-resilience-20261017`
- **Jira Issue**: [EYE-33873](https://tasks.sberdevices.ru/browse/EYE-33873)
- **Criticality**: `S2` (`parent_skill=analyst-teamlead`, downstream panel)
- **Architecture Spec**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`
- **Architecture Packet**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json` (`sha256=86de86783a9eaba1d866955443f59cc31da128d715585456898b9590100ed206`)
- **ARCH_PANEL Proof (Round r2)**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/panel/arch/r2/panel-proof.json` (`sha256=564c5afab8e1890222f84bba898f881826f98d4108758eddf2e13a11820d3e69`)
- **Coder Plan**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/plans/coder-01.json` (`sha256=c33259b6f5fdad2d4d99ba138bbeb623e2034a3391895eb09724a45a294e4273`)
- **ADR Document**: `/Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md`
- **Baseline Git Commit**: `d00d698` (`docs(readme): explain official vendor CLIs vs OAuth proxies (CLIProxyAPI)`)

## 2. Traceability Matrix: Requirements & Arch Decisions (RW-001..RW-010)
| Requirement / Finding | Architecture Decision & Implementation | Implementation Path | Tests |
|---|---|---|---|
| **User Directive 1 & RW-001/002**: Detached turn execution on socket drop (`client_gone`) without killing subagent | `ManagedTurn`, `TurnSessionManager`, `TurnBuffer` ring buffer 10MB, `POST/DELETE /v1/turns/<id>/cancel`, `DETACHED_ORPHAN_TTL_S = 300.0` | `core/turn_session_manager.py`, `server.py` | `tests/test_detached_turn_execution.py`, `tests/test_turn_cancel_and_gap.py` |
| **User Directive 2 & RW-006**: Adaptive idle watchdog (300s) + cputime child monitoring on Darwin + safety cap (3600s) | `AdaptiveTimeoutController`, `ProcessWatchdog` parsing `cputime` across child pgid, fail-closed on `ps` failure | `core/watchdog.py` | `tests/test_adaptive_idle_watchdog.py` |
| **User Directive 3**: Resilience in common hub core layer (`core/`), not per-adapter | Extracted `core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py`, `core/backend_adapter.py` | `core/` | All test suites |
| **RW-003**: Deterministic turn key | `turn_key = sha256(turn_id:rid:session_id)` prevents collision or reuse across rids | `core/turn_session_manager.py` | `tests/test_detached_turn_execution.py` |
| **RW-004**: Gap Replay detection | Buffer evictions return HTTP 410 `GAP_DETECTED` on reattach with stale `Last-Event-ID` | `core/turn_session_manager.py`, `server.py` | `tests/test_turn_cancel_and_gap.py` |
| **RW-005**: Graceful shutdown & drain | `HubLifecycleManager`, non-blocking signal handling via `threading.Event`, drain timeout 110s, 503 `Retry-After: 5` | `core/lifecycle.py`, `server.py` | `tests/test_graceful_shutdown_drain.py` |
| **RW-007**: Safe turn disk serialization | Atomic write to `~/.dsh/turns/<id>.json` with schema version 1.0, 0600 file mode, directory 0700 | `core/turn_session_manager.py` | `tests/test_detached_turn_execution.py` |
| **RW-008**: Security input validation | Strict regex `^[a-zA-Z0-9_-]{1,64}$` on all `turn_id` path and query params | `server.py`, `bridges/muse-bridge/server.py` | `tests/test_turn_cancel_and_gap.py` |
| **RW-009**: Feature flags | `DSH_BRIDGE_DETACHED_ENABLED`, `DSH_BRIDGE_WATCHDOG_ENABLED`, `DSH_BRIDGE_DRAIN_ENABLED` defaults | `server.py` | Unit tests |
| **RW-010**: DSH profile syntax fix | Remove invalid `{{cwd}}` from persona-suffix in `~/.dsh/profiles/web/cordis.patch.yml` | `~/.dsh/profiles/web/cordis.patch.yml` | `tests/test_dsh_profile_config.py` |

## 3. Test Suites & Verification Evidence
- **New Unit Tests** (15 tests, 0.56s execution):
  - `tests/test_detached_turn_execution.py` (4 tests: detached background finish, reattach streaming, disk persistence, memory buffer)
  - `tests/test_adaptive_idle_watchdog.py` (4 tests: idle reset on tokens, safety cap enforcement, Darwin ps parsing, fail-closed)
  - `tests/test_graceful_shutdown_drain.py` (3 tests: SIGTERM signal event, active turn drain, 503 Retry-After rejection)
  - `tests/test_turn_cancel_and_gap.py` (3 tests: explicit cancel endpoint, gap 410 detection, orphan TTL reaper)
  - `tests/test_dsh_profile_config.py` (1 test: cordis patch yml validation)
- **Regression Tests**: 208 existing unit and integration tests passing in 122.8s.
- **Code Linter**: `ruff check` passed without any warnings or errors.

## 4. Full Git Diff (`git diff HEAD`)
```diff
diff --git a/README.md b/README.md
index 32c8f24..f2b7c2b 100644
--- a/README.md
+++ b/README.md
@@ -74,13 +74,13 @@ or script that speaks the OpenAI protocol.
 
 ## Why official vendor CLIs instead of OAuth proxies (CLIProxyAPI)
 
-When direct pay-as-you-go API keys are not used, this hub (`droid exec`, `muse serve`) and its sibling bridges (`claude -p`, `cursor-agent -p`, `agy -p`, `opencode`) spawn the official vendor CLI as a local child process instead of extracting OAuth tokens and calling cloud APIs over raw HTTP like [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) (`cliproxy`).
+This hub contains no OAuth handling. It starts the official vendor CLI as a local child process (`droid exec` for the `droid` backend, `muse exec` for the `muse` backend) and returns that CLI's answer through the OpenAI-compatible API. The sibling bridges (`claude -p`, `cursor-agent -p`, `agy -p`, `opencode`) follow the same pattern but live outside this repository. [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) (`cliproxy`) takes the other route: it stores OAuth logins for many accounts and sends HTTP requests to provider APIs itself.
 
 Replaying subscription tokens through an OAuth proxy carries three risks:
 
-- **Account bans and subscription revocations.** Providers can ban accounts or revoke subscriptions when OAuth tokens issued to an official vendor CLI are replayed from an external OAuth proxy. Spawning the official vendor CLI avoids HTTP client impersonation, though it does not exempt automated usage from each provider's terms of service or guarantee against policy enforcement.
-- **Anthropic and other official vendor CLIs cannot be faithfully reproduced over HTTP.** As shown in CLIProxyAPI's [utls_transport.go](https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/auth/claude/utls_transport.go) and [claude_executor_cloaking.go](https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/runtime/executor/claude_executor_cloaking.go), mimicking Claude Code (`claude`) over raw HTTP requires custom TLS `ClientHello` fingerprints (`utls`), injected `metadata.user_id` values, salted `x-anthropic-billing-header` hashes (`SHA256(salt + messageText[4,7,20] + version)`), and prompt cloaking of sensitive words.
-- **Server-side detection rules change without notice.** Because client checks are enforced on the provider's servers, rotating the fingerprint salt, checking a new header or telemetry field, or flagging cloaked prompts breaks external OAuth proxies or triggers bans without a client release. The trade-off of the local bridge model is operational: each host must install, authenticate, and update the official vendor CLI binaries.
+- **Account bans and subscription revocations.** Providers can ban accounts or revoke subscriptions when OAuth tokens are replayed from an external proxy. Running the official CLI avoids client impersonation, but it does not make automated use allowed under each provider's terms of service, and it does not guarantee against enforcement.
+- **Client imitation is fragile.** To pass as Claude Code over raw HTTP, CLIProxyAPI copies the client's TLS fingerprint for OAuth requests ([utls_transport.go](https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/auth/claude/utls_transport.go)), injects a fake `metadata.user_id`, computes a 3-character build fingerprint for `x-anthropic-billing-header` from a fixed salt, three sampled prompt characters, and the client version, and obfuscates configured sensitive words in prompts ([claude_executor_cloaking.go](https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/runtime/executor/claude_executor_cloaking.go)). Its code targets specific Claude Code versions, and this was checked for Claude Code only.
+- **Server-side detection rules can change at any time.** Client checks run on the provider's servers. A new salt, header, telemetry field, or prompt check can break an external OAuth proxy or get its accounts flagged, with no new client release. The cost of the local-CLI model is operational: each host must install, sign in to, and update the vendor CLI binaries.
 
 ## Supported backends and connected agent CLIs
 
@@ -111,12 +111,13 @@ documented below and in the [port map](#ecosystem-port-and-architecture-map).
 
 ### `muse` — Meta Muse CLI (in-tree hub and dedicated bridge)
 
-- Transport: `muse serve` (MSP — Muse Server Protocol, JSON-RPC over
+- Transport: headless `muse exec` per turn through the launcher wrapper
+  (`~/.config/muse-launch/muse-cli.sh`). The dedicated `muse-bridge` (port
+  `9886`) uses `muse serve` (MSP — Muse Server Protocol, JSON-RPC over
   stdin/stdout) with `approvalMode: "allowAll"` on `session/start`
-  ([ADR 0003](docs/adr/0003-muse-serve-approval-allowall.md)), so interactive
-  multi-step sessions run without a turn reset; headless one-shot `muse exec`
-  through a launcher wrapper remains available. Wonder context is pruned
-  (400k/320k/200k) and net-timeouts are retried.
+  ([ADR 0003](docs/adr/0003-muse-serve-approval-allowall.md)), so its
+  interactive multi-step sessions run without a turn reset. Wonder context is
+  pruned (400k/320k/200k) and net-timeouts are retried.
 - Tool access: Full Access — models can read and write files and run shell
   commands (`--disable-write` / `--disable-shell` are no longer passed).
 - Streaming: live `reasoning_content` with the model's thoughts (`summary.*`
@@ -182,7 +183,7 @@ arbitrary code, so a new CLI always lands as explicit, reviewable code plus
 | Port | Service / bridge | Backend CLI / engine | Models served | Key characteristics |
 |---|---|---|---|---|
 | `:9881` | `claude-p-bridge` | `claude -p` | `claude-opus-5-5`, `claude-haiku-5-5` | Dedicated CLI bridge, tool-calling emulation |
-| `:9882` | `cli-agent-bridge` (hub, this repo) | `droid exec` + `muse serve` | `claude-sonnet-5-5`, `gemini-3.8-flash`, `grok-4.7`, `gpt-6.1-sol`, `muse-wonder-1.0` | Multi-binary hub, resident sessions, catalog schema 3 |
+| `:9882` | `cli-agent-bridge` (hub, this repo) | `droid exec` + `muse exec` | `claude-sonnet-5-5`, `gemini-3.8-flash`, `grok-4.7`, `gpt-6.1-sol`, `muse-wonder-1.0` (Muse enabled only) | Multi-binary hub, resident sessions, catalog schema 3 |
 | `:9884` | `claude-p-sonnet-bridge` | `claude -p` | `claude-sonnet-5-5` | Dedicated Sonnet 5.5 bridge |
 | `:9885` | `grok46-bridge` / `agy-bridge` | `cursor-agent -p` / `agy -p` | `cursor-grok-4.6-high`, `gemini-4-argon` | 500k context, stdin streaming, progressive thinking |
 | `:9886` | `muse-bridge` | `muse serve` + `muse exec` | `muse-wonder-1.0`, `muse-spark-1.3` | MSP JSON-RPC, `allowAll` approval, live reasoning |
diff --git a/adapters/droid_adapter.py b/adapters/droid_adapter.py
index b34b485..1f36fbc 100644
--- a/adapters/droid_adapter.py
+++ b/adapters/droid_adapter.py
@@ -80,7 +80,20 @@ class DroidAdapter(BackendAdapter):
         legacy["rpc"]["items"] = [asdict(item) for item in ctx.rpc.items]
         legacy["images"] = [asdict(image) for image in ctx.images]
         handler = cast(Any, ctx.handler)
-        raw = handler._run_once(legacy, ctx.keepalive, sse_writer)
+        if callable(ctx.on_activity):
+            ctx.on_activity("start")
+        wrapped_writer: Optional[StreamSink] = None
+        if sse_writer is not None:
+
+            def _wrapped_writer(kind: str, text: str) -> bool:
+                if callable(ctx.on_activity):
+                    ctx.on_activity(kind)
+                return sse_writer(kind, text)
+
+            wrapped_writer = _wrapped_writer
+        raw = handler._run_once(legacy, ctx.keepalive, wrapped_writer)
+        if callable(ctx.on_activity):
+            ctx.on_activity("done")
         usage = raw.get("usage") or {}
 
         def tool_call(call: dict) -> ToolCall:
diff --git a/adapters/muse_adapter.py b/adapters/muse_adapter.py
index 3bfd703..ec6da21 100644
--- a/adapters/muse_adapter.py
+++ b/adapters/muse_adapter.py
@@ -57,6 +57,8 @@ from core.backend_adapter import (
     TurnResult,
     Usage,
 )
+from core.watchdog import AdaptiveTimeoutController
+
 
 DEFAULT_WRAPPER = "~/.config/muse-launch/muse-cli.sh"
 DEFAULT_PROXY_PORT = 10816
@@ -529,10 +531,18 @@ class MuseAdapter(BackendAdapter):
         waited = self._acquire_slot(ctx)
         if waited:
             return self._result(waited, 1)
+        managed_turn = getattr(ctx.handler, "_active_managed_turn", None)
+        if managed_turn is not None:
+            with managed_turn._lock:
+                managed_turn._slot_released = False
+                managed_turn._slot_release_fn = self._slots.release
         try:
             return self._run_exec(ctx, prompt)
         finally:
-            self._slots.release()
+            if managed_turn is not None:
+                managed_turn.release_slot_once()
+            else:
+                self._slots.release()
 
     def _run_exec(self, ctx: TurnContext, prompt: str) -> TurnResult:
         model = ctx.model
@@ -565,6 +575,36 @@ class MuseAdapter(BackendAdapter):
         threads: list[threading.Thread] = []
         state = "done"
         timeout_s = self._setting("TIMEOUT_S", 1800.0)
+        cfg_idle = self.config.get("idle_timeout_s")
+        cfg_cap = self.config.get("safety_cap_s")
+        idle_s = (
+            float(cfg_idle)
+            if isinstance(cfg_idle, (int, float)) and not isinstance(cfg_idle, bool)
+            else self._setting("IDLE_TIMEOUT_S", min(300.0, timeout_s))
+        )
+        idle_s = min(idle_s, timeout_s)
+        safety_s = (
+            float(cfg_cap)
+            if isinstance(cfg_cap, (int, float)) and not isinstance(cfg_cap, bool)
+            else self._setting("SAFETY_CAP_S", timeout_s)
+        )
+        if (
+            timeout_s < 300.0
+            and cfg_cap is None
+            and not hasattr(self.host, "SAFETY_CAP_S")
+        ):
+            safety_s = timeout_s
+        watchdog_enabled = os.environ.get(
+            "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "true"
+        ).strip().lower() in ("1", "true", "yes", "on")
+        timeout_ctrl = AdaptiveTimeoutController(
+            idle_timeout_s=idle_s,
+            safety_cap_s=safety_s,
+            finish_reserve_s=0.0 if safety_s <= 60.0 else 35.0,
+            watchdog_enabled=watchdog_enabled,
+            turn_id=ctx.turn_id,
+            log_fn=self._log,
+        )
         pipe_fds: list[int] = []
         try:
             try:
@@ -600,15 +640,19 @@ class MuseAdapter(BackendAdapter):
                 raise OSError("group witness handshake timed out")
             member = int(os.read(ready_r, 32).strip())
             self._register_child(proc.pid, member)
+            if callable(ctx.register_pgid):
+                ctx.register_pgid(proc.pid)
             os.write(gate_w, b"1")
             for fd in (ready_r, gate_w):
                 os.close(fd)
                 pipe_fds.remove(fd)
             if self._shutting_down:  # shutdown успел пройти до регистрации ребёнка
                 self._kill_group(proc)
-            keepalive_s = self._setting("KEEPALIVE_S", 15.0)
+            keepalive_s = min(10.0, self._setting("KEEPALIVE_S", 10.0))
             gone = ctx.client_gone
             keepalive = ctx.keepalive
+            cancel_ev = ctx.cancel_event
+            detach_ok = bool(ctx.detach_on_disconnect)
             stdout, stderr = proc.stdout, proc.stderr
             assert stdout is not None and stderr is not None
             child = proc
@@ -617,24 +661,51 @@ class MuseAdapter(BackendAdapter):
             leader_exited: list[float] = []
 
             def watch() -> None:
-                deadline = time.monotonic() + timeout_s
                 last_ka = time.monotonic()
+                seeded = False
+                detached = False
                 while not done.wait(0.25):
                     now = time.monotonic()
+                    if not seeded:
+                        seeded = True
+                        timeout_ctrl.register_pgid(child.pid)
+                    if cancel_ev is not None and cancel_ev.is_set():
+                        flags["cancelled"] = True
+                        self._kill_group(child)
+                        return
                     if child.poll() is not None:
                         if not leader_exited:
                             leader_exited.append(now)
                         if now - leader_exited[0] >= STDERR_DRAIN_GRACE_S:
                             self._kill_group(child)
                             return
-                    elif now > deadline:
-                        flags["timeout"] = True
-                    elif callable(gone) and gone():
-                        flags["client_gone"] = True
-                    elif callable(keepalive) and now - last_ka >= keepalive_s:
-                        last_ka = now
-                        if not keepalive():
-                            flags["client_gone"] = True
+                    else:
+                        should_stop, wd_reason, _ = timeout_ctrl.check(child.pid)
+                        if should_stop and wd_reason in (
+                            "idle_timeout",
+                            "absolute_cap",
+                        ):
+                            flags["timeout"] = True
+                        elif not detached and callable(gone) and gone():
+                            if detach_ok:
+                                detached = True
+                                if callable(ctx.on_activity):
+                                    ctx.on_activity("detached")
+                            else:
+                                flags["client_gone"] = True
+                        elif (
+                            not detached
+                            and callable(keepalive)
+                            and now - last_ka >= keepalive_s
+                        ):
+                            last_ka = now
+                            if not keepalive():
+                                if detach_ok:
+                                    detached = True
+                                    if callable(ctx.on_activity):
+                                        ctx.on_activity("detached")
+                                else:
+                                    flags["client_gone"] = True
                     if flags:
                         self._kill_group(child)
                         return
@@ -705,6 +776,9 @@ class MuseAdapter(BackendAdapter):
                     line = bytes(pending[:size]).decode("utf-8", "strict")
                     del pending[:size]
                     events.feed_line(line)
+                    timeout_ctrl.record_activity("protocol")
+                    if callable(ctx.on_activity):
+                        ctx.on_activity("protocol")
                     if events.text_bytes > MAX_TURN_TEXT_BYTES:
                         raise ValueError("turn text exceeds the limit")
                 if len(pending) > MAX_LINE_BYTES:
@@ -724,6 +798,7 @@ class MuseAdapter(BackendAdapter):
                 f"muse pump failed: {type(exc).__name__}: {str(exc)[:MAX_ERR_CHARS]}"
             )
         finally:
+            timeout_ctrl.close()
             if proc is not None:
                 # Владение начинается сразу после Popen: даже отказ первого Thread.start
                 # не может обойти kill/wait. Реестр и слот освобождаются ПОСЛЕ группы.
@@ -756,6 +831,8 @@ class MuseAdapter(BackendAdapter):
         err = "\n".join(events.errors + err_lines)[-1000:]
         if events.reason:
             err = (err + f"\nreason: {events.reason}").strip()
+        if flags.get("cancelled"):
+            return self._result("cancelled", 1, err="turn cancelled by user")
         if flags.get("client_gone"):
             return self._result("client_gone", 1)
         if flags.get("timeout"):
@@ -779,6 +856,7 @@ class MuseAdapter(BackendAdapter):
             return self._result("backend_error", rc, err=err)
         return self._result("done", 0, text=events.text, err=err, prompt=prompt)
 
+
     def shutdown(self) -> None:
         """Убить группы процессов собственных детей (только свои PID из реестра адаптера)."""
         self._shutting_down = True
diff --git a/bridges/muse-bridge/server.py b/bridges/muse-bridge/server.py
index 2b010b5..ff19017 100644
--- a/bridges/muse-bridge/server.py
+++ b/bridges/muse-bridge/server.py
@@ -57,13 +57,27 @@ from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from typing import Any, NamedTuple
 
+_REPO_ROOT = Path(__file__).resolve().parents[2]
+if str(_REPO_ROOT) not in sys.path:
+    sys.path.insert(0, str(_REPO_ROOT))
+
+from core.backend_adapter import ToolCall, TurnResult, Usage  # noqa: E402
+from core.lifecycle import HubLifecycleManager  # noqa: E402
+from core.turn_session_manager import (  # noqa: E402
+    GapDetectedError,
+    ManagedTurn,
+    TurnSessionManager,
+    validate_turn_id,
+)
+
 logger = logging.getLogger("muse-bridge")
 
 HOST = os.environ.get("MUSE_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
 PORT = int(os.environ.get("MUSE_BRIDGE_PORT", "9886"))
 AUTH_KEY = os.environ.get("MUSE_BRIDGE_KEY", "").strip()
 
-TIMEOUT_S = float(os.environ.get("MUSE_BRIDGE_TIMEOUT_S", "1800"))
+TIMEOUT_S = float(os.environ.get("MUSE_BRIDGE_TIMEOUT_S", "3600"))
+IDLE_TIMEOUT_S = float(os.environ.get("MUSE_BRIDGE_IDLE_TIMEOUT_S", "300"))
 MAX_CONCURRENT = int(os.environ.get("MUSE_BRIDGE_MAX_CONCURRENT", "2"))
 
 MUSE_WRAPPER = os.environ.get(
@@ -145,7 +159,7 @@ TRANSIENT_RETRY_SCOPE = os.environ.get(
 ).strip()
 FINISH_RESERVE_S = 35.0
 CLOSE_RESERVE_S = 12.0
-REQUEST_CAP_S = 1800.0
+REQUEST_CAP_S = 3600.0
 MIN_ATTEMPT_REMAINING_S = float(os.environ.get("MUSE_BRIDGE_MIN_ATTEMPT_S", "120"))
 CONTROL_WRITE_TIMEOUT_S = 5.0
 LIVE_WRITE_TIMEOUT_S = 3.0
@@ -364,11 +378,54 @@ def _log(msg: str) -> None:
         pass
 
 
-def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
-    hdr = handler.headers.get("Authorization", "")
+def _is_detached_enabled() -> bool:
+    return os.environ.get("BRIDGE_ENABLE_DETACHED_TURNS", "1") not in (
+        "0",
+        "false",
+        "False",
+    )
+
+
+def _is_watchdog_enabled() -> bool:
+    return os.environ.get("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", "1") not in (
+        "0",
+        "false",
+        "False",
+    )
+
+
+def _is_drain_enabled() -> bool:
+    return os.environ.get("BRIDGE_ENABLE_GRACEFUL_DRAIN", "1") not in (
+        "0",
+        "false",
+        "False",
+    )
+
+
+def _extract_auth_token(handler: BaseHTTPRequestHandler) -> str:
+    hdrs = getattr(handler, "headers", None) or {}
+    hdr = hdrs.get("Authorization", "")
     if hdr.startswith("Bearer "):
-        return hdr[7:].strip() == AUTH_KEY
-    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY
+        return hdr[7:].strip()
+    return hdrs.get("x-api-key", "") or hdr.strip()
+
+
+def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
+    return _extract_auth_token(handler) == AUTH_KEY
+
+
+def _owner_token_hash(handler: BaseHTTPRequestHandler) -> str:
+    tok = _extract_auth_token(handler) or AUTH_KEY or "anon"
+    return hashlib.sha256(tok.encode("utf-8", "replace")).hexdigest()
+
+
+TURN_MANAGER = TurnSessionManager(state_root=WORKSPACE / "turns", log_fn=_log)
+LIFECYCLE = HubLifecycleManager(turn_manager=TURN_MANAGER, log_fn=_log)
+
+
+def _reset_state() -> None:
+    TURN_MANAGER.reset()
+    LIFECYCLE.reset_for_tests()
 
 
 def _redact_secrets(text: str) -> str:
@@ -1365,7 +1422,7 @@ SSE_CHUNK_DELAY_S = float(os.environ.get("MUSE_BRIDGE_SSE_CHUNK_DELAY_S", "0.005
 # stream=true: заголовки и role-кадр уходят сразу, пока ход идёт — комментарии keepalive.
 # Без них клиент (OpenAI SDK в DeepSeek Harness) ждал заголовков до своего таймаута
 # (~600 с) и рвал долгий ход как "Request timed out".
-KEEPALIVE_S = float(os.environ.get("MUSE_BRIDGE_KEEPALIVE_S", "15"))
+KEEPALIVE_S = min(10.0, float(os.environ.get("MUSE_BRIDGE_KEEPALIVE_S", "10")))
 
 
 def _split_sse_chunks(text: str, size: int = 0) -> list[str]:
@@ -1532,6 +1589,7 @@ class Run:
         self.approval_seen = False
         self.observed_barrier = False
         self.exec_deadline = float("inf")
+        self.managed_turn: ManagedTurn | None = None
 
     def close(self) -> None:
         """Убить группу процессов хода и коротко дождаться её ухода.
@@ -1637,6 +1695,13 @@ class Run:
                     "err": f"spawn failed: {exc}",
                     "state": "spawn_failed",
                 }
+            if self.managed_turn is not None:
+                self.managed_turn.bind_process(
+                    pgid=self.proc.pid, terminate_fn=self.close
+                )
+                TURN_MANAGER.register_child_pgid(
+                    self.proc.pid, backend="muse", turn_id=self.managed_turn.turn_id
+                )
             self.action_possible = True
 
             def drain_stderr() -> None:
@@ -1674,6 +1739,8 @@ class Run:
                         continue
                     if not isinstance(event, dict):
                         continue
+                    if self.managed_turn is not None:
+                        self.managed_turn.touch_activity("protocol")
                     ptype = str(event.get("payload_type") or "")
                     raw_payload = event.get("payload")
                     payload: dict[str, Any] = (
@@ -1822,6 +1889,7 @@ class ServeRun:
         self.request_deadline = float("inf")
         self.turn_started_at: float | None = None
         self._live_frozen = False
+        self.managed_turn: ManagedTurn | None = None
         # Сквозной live-стриминг всех шагов (ADR-0004): аккумулятор по
         # составному ключу (item_id, idx), единый append-only stream-текст
         # для live/final/flush (S2), доступ — только под _acc_lock (S3).
@@ -2014,6 +2082,13 @@ class ServeRun:
         except OSError as exc:
             raise ServeUnavailable(f"serve spawn failed: {exc}")
         assert self.proc.stdout is not None and self.proc.stdin is not None
+        if self.managed_turn is not None:
+            self.managed_turn.bind_process(
+                pgid=self.proc.pid, terminate_fn=self.close
+            )
+            TURN_MANAGER.register_child_pgid(
+                self.proc.pid, backend="muse", turn_id=self.managed_turn.turn_id
+            )
         # stdin неблокирующий: запись идёт срезами с дедлайном (см. _send).
         os.set_blocking(self.proc.stdin.fileno(), False)
 
@@ -2051,6 +2126,9 @@ class ServeRun:
 
         def read_msg(timeout_at: float) -> dict[str, Any]:
             while time.monotonic() < timeout_at:
+                if self.managed_turn is not None and self.managed_turn.cancel_event.is_set():
+                    self.close()
+                    raise ServeUnavailable("turn cancelled")
                 if self.proc is None or self.proc.stdout is None:
                     raise ServeUnavailable("serve stdout closed")
                 newline = rbuf.find(b"\n")
@@ -2083,6 +2161,8 @@ class ServeRun:
                 except ValueError:
                     continue
                 if isinstance(msg, dict):
+                    if self.managed_turn is not None:
+                        self.managed_turn.touch_activity("protocol")
                     return msg
             raise ServeUnavailable("serve read timeout")
 
@@ -2643,6 +2723,8 @@ class Handler(BaseHTTPRequestHandler):
     # Обрыв клиента и текущий ход: значения инициализируются в setup() каждого соединения.
     _client_gone: bool = False
     _current_run: Run | ServeRun | None = None
+    _active_managed_turn: ManagedTurn | None = None
+    _detach_on_disconnect: bool = False
     # Ранний SSE (stream=true): состояние потока и keepalive текущего соединения.
     _sse_open: bool = False
     _content_started: bool = False
@@ -2669,6 +2751,8 @@ class Handler(BaseHTTPRequestHandler):
         # Состояние обрыва клиента и ссылка на текущий ход — на каждое соединение.
         self._client_gone = False
         self._current_run = None
+        self._active_managed_turn = None
+        self._detach_on_disconnect = False
         self._sse_open = False
         self._content_started = False
         self._sse_id = ""
@@ -2718,7 +2802,11 @@ class Handler(BaseHTTPRequestHandler):
             self._client_gone = True
             self._delivery_failed = True
             _log(message)
-            self._kill_current_run()
+            active_turn = getattr(self, "_active_managed_turn", None)
+            if getattr(self, "_detach_on_disconnect", False) and active_turn is not None:
+                TURN_MANAGER.mark_detached(active_turn.turn_id)
+            else:
+                self._kill_current_run()
         return False
 
     # ---- ранний SSE: заголовки сразу, keepalive во время хода ---------------------
@@ -2823,9 +2911,7 @@ class Handler(BaseHTTPRequestHandler):
         Запись нефатальна (S1): при сбое `_live_degraded=True`, ход жив,
         повторные вызовы коротко возвращают True, буфер уйдёт в финале.
         """
-        if not full_text or not getattr(self, "_sse_open", False):
-            return True
-        if getattr(self, "_live_degraded", False):
+        if not full_text:
             return True
         with self._get_live_lock():
             sent = getattr(self, "_live_sent_text", "")
@@ -2834,6 +2920,15 @@ class Handler(BaseHTTPRequestHandler):
             delta = full_text[len(sent) :]
             if not delta:
                 return True
+            active_turn = getattr(self, "_active_managed_turn", None)
+            if active_turn is not None and not active_turn.buffer.sealed:
+                active_turn.buffer.append("reasoning", delta)
+            if not getattr(self, "_sse_open", False) or getattr(
+                self, "_live_degraded", False
+            ):
+                self._live_sent_text = full_text
+                self._live_reasoning_sent = full_text
+                return True
             ok = self._sse_emit(
                 self._sse_chunk({"reasoning_content": delta}),
                 mark_content=True,
@@ -2922,19 +3017,28 @@ class Handler(BaseHTTPRequestHandler):
         with self._wlock:
             self._sse_phase = "OPEN"
         self.close_connection = True
+        active_turn = getattr(self, "_active_managed_turn", None)
         try:
             self.send_response(200)
             self.send_header("Content-Type", "text/event-stream; charset=utf-8")
             self.send_header("Cache-Control", "no-cache")
             self.send_header("Connection", "close")
             self.send_header("X-Accel-Buffering", "no")
+            if active_turn is not None:
+                self.send_header("X-Turn-Id", active_turn.turn_id)
             self.end_headers()
         except (BrokenPipeError, ConnectionResetError, OSError):
             self._client_gone = True
             _log("client gone before headers")
+            if getattr(self, "_detach_on_disconnect", False) and active_turn is not None:
+                TURN_MANAGER.mark_detached(active_turn.turn_id)
+                return True
             return False
         self._sse_open = True
         if not self._sse_emit(self._sse_chunk({"role": "assistant", "content": ""})):
+            if getattr(self, "_detach_on_disconnect", False) and active_turn is not None:
+                TURN_MANAGER.mark_detached(active_turn.turn_id)
+                return True
             return False
         stop = threading.Event()
         self._keepalive_stop = stop
@@ -3005,7 +3109,7 @@ class Handler(BaseHTTPRequestHandler):
             run.close()
 
     def _watch_client(self, stop: threading.Event) -> None:
-        """Надзор за клиентом во время хода: обрыв -> флаг + killpg группы хода.
+        """Надзор за клиентом во время хода: обрыв -> флаг + killpg группы хода (или detach).
 
         Не выходит после первого убийства: ход может зарегистрироваться (или запустить
         процесс) уже после обрыва — kill идемпотентен и повторяется каждый тик до stop.
@@ -3014,12 +3118,23 @@ class Handler(BaseHTTPRequestHandler):
         while not stop.wait(0.25):
             if self._client_gone or self._client_gone_probe():
                 self._client_gone = True
+                active_turn = getattr(self, "_active_managed_turn", None)
+                if getattr(self, "_detach_on_disconnect", False) and active_turn is not None:
+                    if not reported:
+                        reported = True
+                        _log(
+                            f"client gone during run — detaching turn_id={active_turn.turn_id}"
+                        )
+                    TURN_MANAGER.mark_detached(active_turn.turn_id)
+                    return
                 if not reported:
                     reported = True
                     _log("client gone during run — killing process group")
                 self._kill_current_run()
 
-    def _send(self, code: int, payload: dict) -> None:
+    def _send(
+        self, code: int, payload: dict, headers: dict[str, str] | None = None
+    ) -> None:
         if self._sse_open:
             # Заголовки 200 уже ушли: ошибка — кадром SSE, как у OpenAI-совместимых прокси.
             self._sse_stop_keepalive()
@@ -3057,12 +3172,19 @@ class Handler(BaseHTTPRequestHandler):
             self.send_response(int(code))
             self.send_header("Content-Type", "application/json; charset=utf-8")
             self.send_header("Content-Length", str(len(body)))
+            active_turn = getattr(self, "_active_managed_turn", None)
+            if active_turn is not None and (not headers or "X-Turn-Id" not in headers):
+                self.send_header("X-Turn-Id", active_turn.turn_id)
+            if headers:
+                for hk, hv in headers.items():
+                    self.send_header(str(hk), str(hv))
             self.end_headers()
             self.wfile.write(body)
         except (BrokenPipeError, ConnectionResetError, OSError):
             self._client_gone = True
             _log("client gone before response")
-            self._kill_current_run()
+            if not getattr(self, "_detach_on_disconnect", False):
+                self._kill_current_run()
         finally:
             if have_conn:
                 try:
@@ -3160,12 +3282,82 @@ class Handler(BaseHTTPRequestHandler):
         if self._sse_emit(final):
             self._sse_write("data: [DONE]\n\n")
 
+    def _parse_from_seq(self) -> int | None:
+        raw_seq = None
+        if "?" in self.path:
+            qs = self.path.split("?", 1)[1]
+            for part in qs.split("&"):
+                if part.startswith("from_seq="):
+                    raw_seq = part.split("=", 1)[1]
+                    break
+        if raw_seq is None:
+            hdr_seq = self.headers.get("Last-Event-ID")
+            if hdr_seq is not None and hdr_seq.strip():
+                raw_seq = hdr_seq.strip()
+        if raw_seq is None or raw_seq == "":
+            return 0
+        if not re.fullmatch(r"[0-9]+", str(raw_seq).strip()):
+            return None
+        return int(str(raw_seq).strip())
+
+    def _serve_turn_stream(self, turn_id: str) -> None:
+        if not validate_turn_id(turn_id):
+            self._send(400, {"error": {"message": "invalid turn_id", "code": 400}})
+            return
+        from_seq = self._parse_from_seq()
+        if from_seq is None:
+            self._send(400, {"error": {"message": "invalid from_seq", "code": 400}})
+            return
+        try:
+            turn = TURN_MANAGER.get_turn(
+                turn_id, owner_token_hash=_owner_token_hash(self)
+            )
+        except KeyError:
+            self._send(404, {"error": {"message": f"turn not found: {turn_id}", "code": 404}})
+            return
+        except PermissionError:
+            self._send(403, {"error": {"message": "turn belongs to another token", "code": 403}})
+            return
+        try:
+            turn.buffer.get_since(
+                from_seq,
+                turn_id=turn.turn_id,
+                state_dump_path=turn.state_dump_path,
+            )
+        except GapDetectedError as exc:
+            self._send(410, exc.to_http_payload())
+            return
+        try:
+            self.send_response(200)
+            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
+            self.send_header("Cache-Control", "no-cache")
+            self.send_header("Connection", "close")
+            self.send_header("X-Accel-Buffering", "no")
+            self.send_header("X-Turn-Id", turn.turn_id)
+            self.end_headers()
+            self.close_connection = True
+        except (BrokenPipeError, ConnectionResetError, OSError):
+            return
+        for frame in TURN_MANAGER.iter_sse_stream(
+            turn,
+            from_seq=from_seq,
+            keepalive_interval_s=KEEPALIVE_S,
+            client_gone_fn=self._client_gone_probe,
+        ):
+            try:
+                self.wfile.write(frame.encode("utf-8"))
+                self.wfile.flush()
+            except (BrokenPipeError, ConnectionResetError, OSError):
+                TURN_MANAGER.mark_detached(turn.turn_id)
+                return
+
     def do_GET(self) -> None:  # noqa: N802
         path = self.path.split("?", 1)[0]
         if path in ("/health", "/v1/health"):
             with _active_lock:
                 active = len(_active)
                 quarantined = len(_quarantined_slots)
+            draining = _is_drain_enabled() and LIFECYCLE.is_draining()
             self._send(
                 200,
                 {
@@ -3182,6 +3374,7 @@ class Handler(BaseHTTPRequestHandler):
                     "tool_emulation": True,
                     "uptime_s": int(time.time() - _started),
                 },
+                headers={"X-Bridge-Draining": "1"} if draining else None,
             )
             return
         if not _auth_ok(self):
@@ -3207,9 +3400,38 @@ class Handler(BaseHTTPRequestHandler):
                 },
             )
             return
+        if _is_detached_enabled() and path.startswith("/v1/turns/"):
+            m_stream = re.fullmatch(r"/v1/turns/([^/]+)/stream", path)
+            if m_stream:
+                self._serve_turn_stream(m_stream.group(1))
+                return
+            m_turn = re.fullmatch(r"/v1/turns/([^/]+)", path)
+            if m_turn:
+                turn_id = m_turn.group(1)
+                if not validate_turn_id(turn_id):
+                    self._send(400, {"error": {"message": "invalid turn_id", "code": 400}})
+                    return
+                try:
+                    snap = TURN_MANAGER.get_turn_snapshot(
+                        turn_id, owner_token_hash=_owner_token_hash(self)
+                    )
+                except KeyError:
+                    self._send(
+                        404,
+                        {"error": {"message": f"turn not found: {turn_id}", "code": 404}},
+                    )
+                    return
+                except PermissionError:
+                    self._send(
+                        403,
+                        {"error": {"message": "turn belongs to another token", "code": 403}},
+                    )
+                    return
+                self._send(200, snap)
+                return
         self._send(404, {"error": {"message": f"not found: {path}"}})
 
-    def do_POST(self) -> None:  # noqa: N802
+    def do_DELETE(self) -> None:  # noqa: N802
         if not _auth_ok(self):
             self.close_connection = True
             self._send(
@@ -3217,8 +3439,91 @@ class Handler(BaseHTTPRequestHandler):
             )
             return
         path = self.path.split("?", 1)[0]
+        m_turn = (
+            re.fullmatch(r"/v1/turns/([^/]+)", path)
+            if _is_detached_enabled()
+            else None
+        )
+        if not m_turn:
+            self._send(404, {"error": {"message": f"not found: {path}"}})
+            return
+        turn_id = m_turn.group(1)
+        if not validate_turn_id(turn_id):
+            self._send(400, {"error": {"message": "invalid turn_id", "code": 400}})
+            return
+        owner_hash = _owner_token_hash(self)
+        try:
+            TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
+            snap = TURN_MANAGER.get_turn_snapshot(turn_id, owner_token_hash=owner_hash)
+        except KeyError:
+            self._send(
+                404, {"error": {"message": f"turn not found: {turn_id}", "code": 404}}
+            )
+            return
+        except PermissionError:
+            self._send(
+                403,
+                {"error": {"message": "turn belongs to another token", "code": 403}},
+            )
+            return
+        self._send(200, snap)
+
+    def do_POST(self) -> None:  # noqa: N802
+        self._active_managed_turn = None
+        self._detach_on_disconnect = False
+        path = self.path.split("?", 1)[0]
+        m_cancel = (
+            re.fullmatch(r"/v1/turns/([^/]+)/cancel", path)
+            if _is_detached_enabled()
+            else None
+        )
+        if not m_cancel and _is_drain_enabled() and LIFECYCLE.is_draining():
+            self.close_connection = True
+            self._send(
+                503,
+                {
+                    "error": {
+                        "message": "bridge is shutting down",
+                        "type": "overloaded",
+                        "code": 503,
+                    }
+                },
+                headers={"Retry-After": "5", "X-Bridge-Draining": "1"},
+            )
+            return
+        if not _auth_ok(self):
+            self.close_connection = True
+            self._send(
+                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
+            )
+            return
         length = int(self.headers.get("Content-Length") or "0")
         raw = self.rfile.read(length) if length else b"{}"
+        if m_cancel is not None:
+            turn_id = m_cancel.group(1)
+            if not validate_turn_id(turn_id):
+                self._send(400, {"error": {"message": "invalid turn_id", "code": 400}})
+                return
+            owner_hash = _owner_token_hash(self)
+            try:
+                TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
+                snap = TURN_MANAGER.get_turn_snapshot(
+                    turn_id, owner_token_hash=owner_hash
+                )
+            except KeyError:
+                self._send(
+                    404,
+                    {"error": {"message": f"turn not found: {turn_id}", "code": 404}},
+                )
+                return
+            except PermissionError:
+                self._send(
+                    403,
+                    {"error": {"message": "turn belongs to another token", "code": 403}},
+                )
+                return
+            self._send(200, snap)
+            return
         try:
             req = json.loads(raw.decode("utf-8") or "{}")
         except ValueError:
@@ -3239,6 +3544,10 @@ class Handler(BaseHTTPRequestHandler):
             self._exec_deadline = float("inf")
             self._request_deadline = float("inf")
             self._delivery_failed = False
+            if self._active_managed_turn is not None and not self._detach_on_disconnect:
+                TURN_MANAGER.finalize_abandoned_turn(self._active_managed_turn)
+            self._active_managed_turn = None
+            self._detach_on_disconnect = False
 
     def _serve_json(self, req: dict) -> None:
         # Абсолютный бюджет запроса a4: t0 при приёме, до очереди и вычислений.
@@ -3282,6 +3591,32 @@ class Handler(BaseHTTPRequestHandler):
             )
             return
 
+        extra = (
+            req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
+        )
+        cwd = str(extra.get("cwd") or "")
+        _hdrs = getattr(self, "headers", None) or {}
+        req_turn_id = (
+            _hdrs.get("X-Turn-Id") or str(extra.get("turn_id") or "")
+        ).strip()
+        resume_turn_id = (
+            _hdrs.get("X-Resume-Turn-Id")
+            or str(extra.get("resume_turn_id") or "")
+        ).strip()
+        for candidate_tid in (req_turn_id, resume_turn_id):
+            if candidate_tid and not validate_turn_id(candidate_tid):
+                self._send(
+                    400,
+                    {
+                        "error": {
+                            "message": "invalid turn_id",
+                            "type": "invalid_request_error",
+                            "code": 400,
+                        }
+                    },
+                )
+                return
+
         raw_tools = req.get("tools")
         tools = (
             [t for t in raw_tools if isinstance(t, dict)]
@@ -3356,21 +3691,81 @@ class Handler(BaseHTTPRequestHandler):
         reflected_prompts: list[str] = [prompt]
 
         effort = _map_effort(req)
+        raw_key = req.get("prompt_cache_key")
+        session_id = str(raw_key) if isinstance(raw_key, str) else ""
+        self._detach_on_disconnect = _is_detached_enabled() and bool(
+            req_turn_id or resume_turn_id or session_id
+        )
+        managed_turn: ManagedTurn | None = None
+        attached_existing = False
+        if _is_detached_enabled():
+            try:
+                managed_turn, attached_existing = TURN_MANAGER.create_or_attach_turn(
+                    model=model,
+                    backend="muse",
+                    cwd=cwd,
+                    messages=raw_messages if isinstance(raw_messages, list) else [],
+                    session_id=session_id,
+                    owner_token_hash=_owner_token_hash(self),
+                    rid=rid,
+                    requested_turn_id=req_turn_id or None,
+                    resume_turn_id=resume_turn_id or None,
+                    stream=req.get("stream") is True,
+                    emulate_tools=emulate_tools,
+                    idle_timeout_s=IDLE_TIMEOUT_S if _is_watchdog_enabled() else TIMEOUT_S,
+                    safety_cap_s=TIMEOUT_S,
+                )
+            except PermissionError:
+                self._send(
+                    403,
+                    {
+                        "error": {
+                            "message": "turn belongs to another token",
+                            "type": "forbidden",
+                            "code": 403,
+                        }
+                    },
+                )
+                return
+            except ValueError as exc:
+                self._send(
+                    400,
+                    {
+                        "error": {
+                            "message": str(exc),
+                            "type": "invalid_request_error",
+                            "code": 400,
+                        }
+                    },
+                )
+                return
+        self._active_managed_turn = managed_turn
+        if attached_existing and managed_turn is not None:
+            if req.get("stream") is True:
+                self._serve_turn_stream(managed_turn.turn_id)
+                return
+            managed_turn.done_event.wait(timeout=TIMEOUT_S)
+            snap = TURN_MANAGER.get_turn_snapshot(
+                managed_turn.turn_id, owner_token_hash=_owner_token_hash(self)
+            )
+            self._send(200, snap)
+            return
 
         if req.get("stream") is True and not self._sse_begin(model):
             return
         while not _slots.acquire(timeout=1.0):
             if self._client_gone or self._client_gone_probe():
                 self._client_gone = True
-                _log("client gone while waiting for a slot")
-                return
+                if not self._detach_on_disconnect:
+                    _log("client gone while waiting for a slot")
+                    return
             if time.monotonic() >= _exec_deadline - MIN_ATTEMPT_REMAINING_S:
                 _log("insufficient remaining budget while waiting for a slot")
                 self._send(
                     503, {"error": {"message": "bridge busy", "type": "overloaded"}}
                 )
                 return
-        if self._client_gone or self._client_gone_probe():
+        if (self._client_gone or self._client_gone_probe()) and not self._detach_on_disconnect:
             # Клиент ушёл на границе получения слота: ход без надзора не стартует.
             self._client_gone = True
             _log("client gone while waiting for a slot")
@@ -3381,6 +3776,16 @@ class Handler(BaseHTTPRequestHandler):
             _slots.release()
             self._send(503, {"error": {"message": "bridge busy", "type": "overloaded"}})
             return
+        slot_released = [False]
+
+        def _release_slot_once() -> None:
+            if not slot_released[0]:
+                slot_released[0] = True
+                _slots.release()
+
+        if managed_turn is not None:
+            managed_turn._slot_release_fn = _release_slot_once
+
         watch_stop = threading.Event()
         watcher = threading.Thread(
             target=self._watch_client, args=(watch_stop,), daemon=True
@@ -3429,12 +3834,15 @@ class Handler(BaseHTTPRequestHandler):
                 agg["observed"] = agg["observed"] or bool(observed)
 
         def _can_start(is_exec: bool, *, context: bool = False) -> tuple[bool, str]:
+            if managed_turn is not None and managed_turn.cancel_event.is_set():
+                return False, "client_gone"
             if self._client_gone or self._client_gone_probe():
                 self._client_gone = True
-                return False, "client_gone"
+                if not self._detach_on_disconnect:
+                    return False, "client_gone"
             if getattr(self, "_content_started", False):
                 return False, "content_started"
-            if getattr(self, "_delivery_failed", False):
+            if getattr(self, "_delivery_failed", False) and not self._detach_on_disconnect:
                 return False, "delivery_failed"
             if agg["degraded"]:
                 return False, "approval_degraded"
@@ -3478,10 +3886,11 @@ class Handler(BaseHTTPRequestHandler):
             # S4: новый ServeRun (в т.ч. ретрай) стартует с чистого live-префикса.
             self._reset_live_for_attempt()
             serve_run = ServeRun(model, attempt_prompt, effort, WORKSPACE)
+            serve_run.managed_turn = managed_turn
             serve_run.exec_deadline = _exec_deadline
             serve_run.write_deadline = _write_deadline
             serve_run.request_deadline = _req_deadline
-            if req.get("stream") is True and self._sse_open:
+            if req.get("stream") is True and (self._sse_open or self._detach_on_disconnect):
                 serve_run.live_sink = self._live_reasoning_sink
             runs.append(serve_run)
             self._current_run = serve_run
@@ -3492,7 +3901,17 @@ class Handler(BaseHTTPRequestHandler):
                 return attempt_out, "serve"
             except ServeUnavailable as exc:
                 _update_agg(serve_run, None)
-                if self._client_gone:
+                if managed_turn is not None and managed_turn.cancel_event.is_set():
+                    return (
+                        {
+                            "rc": -1,
+                            "text": "",
+                            "err": "turn cancelled",
+                            "state": "client_gone",
+                        },
+                        "aborted",
+                    )
+                if self._client_gone and not self._detach_on_disconnect:
                     _log("client gone during serve — exec fallback skipped")
                     return (
                         {
@@ -3541,6 +3960,7 @@ class Handler(BaseHTTPRequestHandler):
                     return _blocked_out(err), "serve"
                 _log(f"serve unavailable ({safe_exc}), fallback exec model={model}")
                 exec_run = Run(model, attempt_prompt, effort, WORKSPACE)
+                exec_run.managed_turn = managed_turn
                 exec_run.exec_deadline = _exec_deadline
                 exec_run.action_possible = True
                 agg["action"] = True
@@ -3562,7 +3982,11 @@ class Handler(BaseHTTPRequestHandler):
             while True:
                 if out.get("rc") == 0 and out.get("state") == "ok":
                     break
-                if self._client_gone or getattr(self, "_delivery_failed", False):
+                if (
+                    self._client_gone or getattr(self, "_delivery_failed", False)
+                ) and not self._detach_on_disconnect:
+                    break
+                if managed_turn is not None and managed_turn.cancel_event.is_set():
                     break
                 raw_err = str(out.get("err") or "")
                 is_hard_threshold = (
@@ -3632,7 +4056,9 @@ class Handler(BaseHTTPRequestHandler):
                             f"target={retry_target})"
                         )
                         break
-                    if self._client_gone or self._client_gone_probe():
+                    if (
+                        self._client_gone or self._client_gone_probe()
+                    ) and not self._detach_on_disconnect:
                         self._client_gone = True
                         break
                     context_retry_count = 1
@@ -3705,7 +4131,9 @@ class Handler(BaseHTTPRequestHandler):
                 pause_end = min(time.monotonic() + pause, _exec_deadline)
                 client_left = False
                 while time.monotonic() < pause_end:
-                    if self._client_gone or self._client_gone_probe():
+                    if (
+                        self._client_gone or self._client_gone_probe()
+                    ) and not self._detach_on_disconnect:
                         self._client_gone = True
                         client_left = True
                         break
@@ -3723,12 +4151,16 @@ class Handler(BaseHTTPRequestHandler):
             for run in runs:
                 run.close()
             if all(run.dead_confirmed for run in runs):
-                _slots.release()
-            else:
+                if managed_turn is not None:
+                    managed_turn.release_slot_once()
+                else:
+                    _release_slot_once()
+            elif not slot_released[0]:
                 # Смерть группы не подтверждена: слот не освобождается, пока она жива (карантин).
+                slot_released[0] = True
                 _quarantine_slot([run for run in runs if not run.dead_confirmed])
 
-        if self._client_gone:
+        if self._client_gone and not self._detach_on_disconnect:
             # Клиент ушёл: ответ в закрытый сокет не пишется (ни JSON, ни кадр ошибки).
             _log("client gone — response skipped")
             return
@@ -3740,6 +4172,41 @@ class Handler(BaseHTTPRequestHandler):
         if terminal_context_err is not None:
             diagnostic = _redact_secrets(terminal_context_err)
         out["err"] = _redact_secrets(diagnostic)
+
+        # Завершение управляемого хода в TurnSessionManager (для polling/replay после отсоединения).
+        if managed_turn is not None:
+            raw_content = str(out.get("text") or "")
+            parsed_content = raw_content
+            parsed_calls: list[dict] = []
+            if emulate_tools and raw_content and out.get("state") == "ok" and out.get("rc") == 0:
+                parsed_content, parsed_calls = _split_tool_calls(
+                    out.get("chunks") or [raw_content]
+                )
+            p_tok = _estimate_usage_tokens(prompt)
+            c_tok = _estimate_usage_tokens(raw_content)
+            t_res = TurnResult(
+                state="done" if (out.get("state") == "ok" and out.get("rc") == 0) else str(out.get("state") or "backend_error"),
+                rc=int(out.get("rc") or 0),
+                text=parsed_content,
+                err=str(out.get("err") or ""),
+                usage=Usage(input_tokens=p_tok, output_tokens=c_tok),
+                tool_calls=tuple(
+                    ToolCall(
+                        index=int(tc.get("index", idx)),
+                        id=str(tc.get("id", f"call_{idx}")),
+                        type="function",
+                        function=dict(tc.get("function") or {}),
+                    )
+                    for idx, tc in enumerate(parsed_calls)
+                ),
+            )
+            TURN_MANAGER.complete_turn_from_result(
+                managed_turn, t_res, backend_kind="muse"
+            )
+
+        if self._client_gone:
+            _log("client gone (detached turn finalized) — response skipped")
+            return
         if out.get("state") in ("launcher_missing", "spawn_failed"):
             _log(_format_err_log(model, via, out, req.get("stream") is True))
             self._send(
@@ -3909,10 +4376,14 @@ def main() -> int:
         WORKSPACE.mkdir(parents=True, exist_ok=True)
     except OSError as exc:
         _log(f"workspace mkdir failed: {exc}")
+    LIFECYCLE.reap_startup_orphans()
     _log(
         f"start host={HOST} port={PORT} models={sorted(ALLOWED_MODELS)} wrapper={MUSE_WRAPPER}"
     )
     server = Server((HOST, PORT), Handler)
+    if _is_drain_enabled():
+        LIFECYCLE.install_signal_handlers()
+        LIFECYCLE.start_signal_watcher(server)
     try:
         server.serve_forever()
     except KeyboardInterrupt:
@@ -3924,3 +4395,4 @@ def main() -> int:
 
 if __name__ == "__main__":
     raise SystemExit(main())
+
diff --git a/core/backend_adapter.py b/core/backend_adapter.py
index 5fa028d..752e2c2 100644
--- a/core/backend_adapter.py
+++ b/core/backend_adapter.py
@@ -97,6 +97,15 @@ class TurnContext:
     handler: object | None = None
     keepalive: PollCallback | None = None
     client_gone: PollCallback | None = None
+    rid: str = ""
+    turn_id: str = ""
+    idle_timeout_s: float = 300.0
+    safety_cap_s: float = 3600.0
+    on_activity: Callable[[str], None] | None = None
+    register_pgid: Callable[[int], None] | None = None
+    managed_turn: Any = None
+    detach_on_disconnect: bool = False
+    cancel_event: Any = None
 
 
 @dataclass(frozen=True)
@@ -171,6 +180,8 @@ BACKEND_KEYS = frozenset(
         "wrapper",
         "technical_ref",
         "proxy_port",
+        "idle_timeout_s",
+        "safety_cap_s",
     }
 )
 TECHNICAL_REF_KEYS = frozenset({"version", "binary_path", "binary_sha256"})
@@ -221,6 +232,15 @@ def backend_entry_error(backend_id: Any, entry: Any, kinds: Mapping[str, Any]) -
             or not PROXY_PORT_MIN <= port <= PROXY_PORT_MAX
         ):
             return "backend_proxy_port_invalid"
+    for timeout_key in ("idle_timeout_s", "safety_cap_s"):
+        if timeout_key in entry and entry[timeout_key] is not None:
+            timeout_val = entry[timeout_key]
+            if (
+                isinstance(timeout_val, bool)
+                or not isinstance(timeout_val, (int, float))
+                or timeout_val <= 0
+            ):
+                return f"backend_{timeout_key}_invalid"
     if "technical_ref" not in entry:
         return "backend_technical_ref_missing" if kind in PIN_REQUIRED_KINDS else ""
     ref = entry.get("technical_ref")
diff --git a/core/lifecycle.py b/core/lifecycle.py
new file mode 100644
index 0000000..b27672e
--- /dev/null
+++ b/core/lifecycle.py
@@ -0,0 +1,486 @@
+"""Менеджер жизненного цикла хаба, неблокирующий Drain и уборка сирот (ADR-0005 / AD-004).
+
+Модуль отвечает за:
+1. Неблокирующий перехват `SIGTERM`/`SIGINT` (`RW-007`): обработчик сигнала выставляет
+   только `threading.Event` (`shutdown_requested`), не захватывая мьютексы и не
+   выполняя блокирующий ввод-вывод.
+2. Координацию `DRAINING` в фоновом потоке (`DRAIN_TIMEOUT_S = 110.0` с при
+   `ExitTimeOut = 120` с в launchd): новые запросы получают `HTTP 503 Service Unavailable`
+   с заголовком `Retry-After: 5`, `/health` возвращает `ok: false` и заголовок
+   `X-Bridge-Draining: true`, а активные ходы доводятся до конца либо корректно
+   прерываются со сбросом `reasoning_content` и терминальным чанком `drain_timeout`.
+3. Безопасную уборку сирот при старте (`reap_orphans_on_startup`, `RW-004`): сверка
+   `workspace/state/children.json` через `os.kill(pid, 0)` и имя команды в `ps`,
+   мягкое погашение `SIGTERM -> 1s -> SIGKILL` с логом `orphan_reaped`.
+4. Контроль интервала SSE keepalive (`KeepaliveController`, `<= 10.0` с).
+"""
+
+from __future__ import annotations
+
+from collections.abc import Callable
+import json
+import os
+from pathlib import Path
+import signal
+import subprocess
+import threading
+import time
+from typing import Any
+
+from core.turn_session_manager import (
+    SNAPSHOT_SCHEMA_VERSION,
+    TurnSessionManager,
+    _atomic_write_json_0600,
+)
+
+DRAIN_TIMEOUT_S: float = 110.0
+DEFAULT_DRAIN_SECONDS: float = DRAIN_TIMEOUT_S
+RETRY_AFTER_S: int = 5
+ORPHAN_SIGTERM_GRACE_S: float = 1.0
+MAX_KEEPALIVE_INTERVAL_S: float = 10.0
+
+KNOWN_CHILD_BINARIES = frozenset(
+    {
+        "muse",
+        "muse-cli",
+        "muse-cli.sh",
+        "droid",
+        "fake_droid",
+        "fake_serve",
+        "node",
+        "python",
+        "python3",
+        "bash",
+        "sh",
+        "zsh",
+        "sleep",
+    }
+)
+
+
+class DrainState:
+    """Фазы жизненного цикла HTTP-хаба при перезапуске."""
+
+    READY = "READY"
+    DRAINING = "DRAINING"
+    STOPPED = "STOPPED"
+
+
+class KeepaliveController:
+    """Контроллер интервала SSE keepalive (`<= 10.0` с для защиты от обрыва прокси/туннеля)."""
+
+    def __init__(self, max_interval_s: float = MAX_KEEPALIVE_INTERVAL_S) -> None:
+        self.max_interval_s = max(0.05, min(float(max_interval_s), MAX_KEEPALIVE_INTERVAL_S))
+
+    def effective_interval(self, requested_s: float | int | None = None) -> float:
+        """Возвращает эффективный интервал keepalive, не превышающий `10.0` с."""
+        if requested_s is None:
+            return self.max_interval_s
+        try:
+            val = float(requested_s)
+        except (TypeError, ValueError):
+            return self.max_interval_s
+        if val <= 0:
+            return self.max_interval_s
+        return min(val, self.max_interval_s)
+
+    @staticmethod
+    def sse_comment() -> str:
+        """Возвращает стандартный SSE-комментарий keepalive."""
+        return ": keepalive\n\n"
+
+    @staticmethod
+    def sse_data_chunk(
+        *,
+        completion_id: str,
+        created: int,
+        model: str,
+    ) -> str:
+        """Возвращает пустой SSE data-чанк keepalive в формате OpenAI `chat.completion.chunk`."""
+        payload = json.dumps(
+            {
+                "id": completion_id,
+                "object": "chat.completion.chunk",
+                "created": int(created),
+                "model": model,
+                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
+            },
+            ensure_ascii=False,
+        )
+        return f"data: {payload}\n\n"
+
+
+class HubLifecycleManager:
+    """Координатор сигналов `SIGTERM`/`SIGINT`, фазы `DRAINING` и уборки сирот."""
+
+    def __init__(
+        self,
+        workspace: Path | str | Callable[[], Path] | None = None,
+        *,
+        state_dir: Path | str | Callable[[], Path] | None = None,
+        turn_manager: TurnSessionManager | None = None,
+        active_turns_fn: Callable[[], int] | None = None,
+        force_kill_fn: Callable[[], None] | None = None,
+        drain_timeout_s: float = DRAIN_TIMEOUT_S,
+        retry_after_s: int = RETRY_AFTER_S,
+        orphan_grace_s: float = ORPHAN_SIGTERM_GRACE_S,
+        drain_enabled_fn: Callable[[], bool] | None = None,
+        log_fn: Callable[[str], None] | None = None,
+        on_shutdown_complete: Callable[[], None] | None = None,
+    ) -> None:
+        ws_source = workspace if workspace is not None else (state_dir or ".")
+        self._explicit_state_dir = state_dir
+        self._workspace_fn: Callable[[], Path] = (
+            (lambda: Path(ws_source))
+            if isinstance(ws_source, (str, Path))
+            else ws_source
+        )
+        self.turn_manager = turn_manager
+        self._active_turns_fn = active_turns_fn
+        self.drain_timeout_s = float(drain_timeout_s)
+        self.retry_after_s = int(retry_after_s)
+        self.orphan_grace_s = float(orphan_grace_s)
+        self._drain_enabled_fn = drain_enabled_fn or (
+            lambda: os.environ.get(
+                "BRIDGE_DRAIN_ON_SHUTDOWN",
+                os.environ.get("DSH_BRIDGE_DRAIN_ENABLED", "true"),
+            )
+            .strip()
+            .lower()
+            in ("1", "true", "yes", "on")
+        )
+        self._log_fn = log_fn
+        self._on_shutdown_complete = on_shutdown_complete or force_kill_fn
+
+
+        self.shutdown_requested = threading.Event()
+        self.drain_started = threading.Event()
+        self.drain_completed = threading.Event()
+        self.state: str = DrainState.READY
+        self.last_signal: int | None = None
+
+        self._lock = threading.Lock()
+        self._server: Any = None
+        self._drain_thread: threading.Thread | None = None
+        self.keepalive = KeepaliveController()
+
+    @property
+    def workspace(self) -> Path:
+        return Path(self._workspace_fn())
+
+    @property
+    def children_path(self) -> Path:
+        if self.turn_manager is not None:
+            return self.turn_manager.children_path
+        if self._explicit_state_dir is not None:
+            sd = Path(
+                self._explicit_state_dir()
+                if callable(self._explicit_state_dir)
+                else self._explicit_state_dir
+            )
+            if (sd / "children.json").exists() or not (sd / "state").is_dir():
+                return sd / "children.json"
+        return self.workspace / "state" / "children.json"
+
+    def is_draining(self) -> bool:
+        return (
+            self.state in (DrainState.DRAINING, DrainState.STOPPED)
+            or self.shutdown_requested.is_set()
+        )
+
+    def is_drain_enabled(self) -> bool:
+        return bool(self._drain_enabled_fn())
+
+    def _log(self, message: str) -> None:
+        if self._log_fn is not None:
+            try:
+                self._log_fn(message)
+            except Exception:  # noqa: BLE001
+                pass
+
+    def attach_server(self, server: Any) -> None:
+        """Привязывает экземпляр `ThreadingHTTPServer` для остановки после drain."""
+        with self._lock:
+            self._server = server
+
+    def start_signal_watcher(self, server: Any = None) -> threading.Thread:
+        """Привязывает HTTP-сервер и запускает фоновый поток координации drain."""
+        if server is not None:
+            self.attach_server(server)
+        return self.start_drain_worker()
+
+    def handle_signal(self, signum: int, _frame: Any = None) -> None:
+        """Неблокирующий обработчик `SIGTERM`/`SIGINT` (RW-007).
+
+        В обработчике сигнала запрещены захват `Lock`, логирование и I/O:
+        выставляется только атомарный `threading.Event`.
+        """
+        self.last_signal = int(signum)
+        self.shutdown_requested.set()
+
+    def start_drain_worker(self) -> threading.Thread:
+        """Запускает фоновый поток, ожидающий `shutdown_requested`."""
+        with self._lock:
+            if self._drain_thread is not None and self._drain_thread.is_alive():
+                return self._drain_thread
+            worker = threading.Thread(
+                target=self._drain_worker_loop,
+                name="hub-drain-coordinator",
+                daemon=True,
+            )
+            self._drain_thread = worker
+            worker.start()
+            return worker
+
+    def install_signal_handlers(self, *, start_worker: bool = True) -> None:
+        """Регистрирует `handle_signal` для `SIGTERM`/`SIGINT` и запускает drain-поток."""
+        if start_worker:
+            self.start_drain_worker()
+        if threading.current_thread() is threading.main_thread():
+            signal.signal(signal.SIGTERM, self.handle_signal)
+            signal.signal(signal.SIGINT, self.handle_signal)
+
+    def trigger_shutdown(self, signum: int = signal.SIGTERM) -> None:
+        """Инициирует процедуру Graceful Shutdown & Drain (безопасно из любого потока)."""
+        self.start_drain_worker()
+        self.handle_signal(signum, None)
+
+    def _drain_worker_loop(self) -> None:
+        self.shutdown_requested.wait()
+        self.run_drain_once()
+
+    def run_drain_once(self) -> dict[str, Any]:
+        """Выполняет фазу `DRAINING` в фоновом потоке (идемпотентно)."""
+        with self._lock:
+            if self.state in (DrainState.DRAINING, DrainState.STOPPED):
+                return {"interrupted_turn_ids": [], "state": self.state}
+            self.state = DrainState.DRAINING
+            self.drain_started.set()
+            srv = self._server
+
+        eff_timeout = self.drain_timeout_s if self.is_drain_enabled() else 0.0
+        active_before = (
+            self.turn_manager.active_count()
+            if self.turn_manager is not None
+            else (self._active_turns_fn() if self._active_turns_fn is not None else 0)
+        )
+        self._log(
+            f"drain_started signal={self.last_signal or 0} "
+            f"active_turns={active_before} timeout_s={eff_timeout:.1f}"
+        )
+
+        remaining = []
+        deadline = time.monotonic() + max(0.0, eff_timeout)
+        if self.turn_manager is not None:
+            if eff_timeout > 0:
+                remaining = self.turn_manager.wait_for_active_turns(timeout=eff_timeout)
+            else:
+                remaining = self.turn_manager.active_turns()
+
+            for turn in remaining:
+                self._log(
+                    f"drain_timeout_interrupt rid={turn.rid} turn_id={turn.turn_id} "
+                    f"pgid={turn.pgid}"
+                )
+                self.turn_manager.interrupt_for_drain(
+                    turn,
+                    message="bridge restart drain timeout exceeded",
+                )
+        elif self._active_turns_fn is not None and eff_timeout > 0:
+            while time.monotonic() < deadline and self._active_turns_fn() > 0:
+                time.sleep(0.05)
+
+        if srv is not None:
+            try:
+                srv.shutdown()
+            except Exception:  # noqa: BLE001
+                pass
+
+        if self._on_shutdown_complete is not None:
+            try:
+                self._on_shutdown_complete()
+            except Exception:  # noqa: BLE001
+                pass
+
+        with self._lock:
+            self.state = DrainState.STOPPED
+            self.drain_completed.set()
+        self._log(f"drain_completed interrupted_turns={len(remaining)}")
+        return {
+            "interrupted_turn_ids": [t.turn_id for t in remaining],
+            "state": self.state,
+        }
+
+    def draining_response(self) -> tuple[int, dict[str, str], dict[str, Any]]:
+        """Возвращает `(status_code, headers, body)` для отказа новым запросам при `DRAINING`."""
+        headers = {
+            "Retry-After": str(self.retry_after_s),
+            "X-Bridge-Draining": "true",
+        }
+        body = {
+            "error": {
+                "message": "bridge is draining for restart",
+                "type": "overloaded",
+                "code": 503,
+            }
+        }
+        return 503, headers, body
+
+    def health_headers(self) -> dict[str, str]:
+        """Возвращает дополнительные HTTP-заголовки для `/health` в режиме `DRAINING`."""
+        if self.is_draining():
+            return {"X-Bridge-Draining": "true"}
+        return {}
+
+    @staticmethod
+    def _is_pid_or_group_alive(pid: int, pgid: int) -> bool:
+        for target, fn in ((pgid, os.killpg), (pid, os.kill)):
+            if isinstance(target, int) and target > 0:
+                try:
+                    fn(target, 0)
+                    return True
+                except ProcessLookupError:
+                    continue
+                except PermissionError:
+                    return True
+                except OSError:
+                    continue
+        return False
+
+    @staticmethod
+    def _matches_expected_command(pid: int, pgid: int, expected_cmd: str = "") -> bool:
+        """Проверяет через `ps`, что процесс принадлежит CLI-потомку моста, а не чужому PID."""
+        targets = []
+        if isinstance(pid, int) and pid > 0:
+            targets.append(("-p", str(pid)))
+        if isinstance(pgid, int) and pgid > 0:
+            targets.append(("-g", str(pgid)))
+        if not targets:
+            return False
+
+        for flag, val in targets:
+            try:
+                proc = subprocess.run(
+                    ["ps", "-o", "comm=,command=", flag, val],
+                    capture_output=True,
+                    text=True,
+                    timeout=2.0,
+                    check=False,
+                )
+            except (subprocess.TimeoutExpired, OSError):
+                continue
+            if proc.returncode != 0 or not proc.stdout.strip():
+                continue
+            out_lower = proc.stdout.lower()
+            if expected_cmd and expected_cmd.lower() in out_lower:
+                return True
+            for token in KNOWN_CHILD_BINARIES:
+                if token in out_lower:
+                    return True
+        return False
+
+    def reap_orphans_on_startup(
+        self, children_file: Path | None = None
+    ) -> list[int]:
+        """Убирает осиротевшие группы процессов из `children.json` при старте хаба (RW-004)."""
+        path = Path(children_file) if children_file is not None else self.children_path
+        if not path.is_file():
+            return []
+
+        try:
+            raw = json.loads(path.read_text(encoding="utf-8"))
+        except (OSError, json.JSONDecodeError):
+            return []
+
+        entries: list[dict[str, Any]] = []
+        if isinstance(raw, dict):
+            if isinstance(raw.get("children"), list):
+                entries = [item for item in raw["children"] if isinstance(item, dict)]
+            else:
+                for key, val in raw.items():
+                    if key == "schema_version":
+                        continue
+                    if isinstance(val, dict):
+                        entry = dict(val)
+                        if "pid" not in entry and str(key).isdigit():
+                            entry["pid"] = int(key)
+                        entries.append(entry)
+                    elif isinstance(val, int) and str(key).isdigit():
+                        entries.append({"pid": int(key), "pgid": int(val)})
+        elif isinstance(raw, list):
+            for item in raw:
+                if isinstance(item, dict):
+                    entries.append(item)
+                elif isinstance(item, int):
+                    entries.append({"pid": item, "pgid": item})
+
+        reaped_pgids: list[int] = []
+        seen_pgids: set[int] = set()
+        for entry in entries:
+            pid = int(entry.get("pid") or entry.get("pgid") or 0)
+            pgid = int(entry.get("pgid") or pid or 0)
+            turn_id = str(entry.get("turn_id") or "-")
+            expected_cmd = str(entry.get("command") or entry.get("cmd") or "")
+            if pgid <= 0 or pgid in seen_pgids:
+                continue
+            seen_pgids.add(pgid)
+            if not self._is_pid_or_group_alive(pid, pgid):
+                continue
+            if not self._matches_expected_command(pid, pgid, expected_cmd):
+                continue
+
+            try:
+                os.killpg(pgid, signal.SIGTERM)
+            except (ProcessLookupError, PermissionError, OSError):
+                try:
+                    if pid > 0:
+                        os.kill(pid, signal.SIGTERM)
+                except (ProcessLookupError, PermissionError, OSError):
+                    pass
+
+            deadline = time.monotonic() + max(0.05, self.orphan_grace_s)
+            while time.monotonic() < deadline:
+                if not self._is_pid_or_group_alive(pid, pgid):
+                    break
+                time.sleep(0.05)
+
+            if self._is_pid_or_group_alive(pid, pgid):
+                try:
+                    os.killpg(pgid, signal.SIGKILL)
+                except (ProcessLookupError, PermissionError, OSError):
+                    try:
+                        if pid > 0:
+                            os.kill(pid, signal.SIGKILL)
+                    except (ProcessLookupError, PermissionError, OSError):
+                        pass
+
+            reaped_pgids.append(pgid)
+            self._log(f"orphan_reaped pgid={pgid} turn_id={turn_id}")
+
+        try:
+            empty_payload: Any = (
+                []
+                if isinstance(raw, list)
+                else {"schema_version": SNAPSHOT_SCHEMA_VERSION, "children": []}
+            )
+            _atomic_write_json_0600(path, empty_payload)
+        except OSError:
+            pass
+
+        return reaped_pgids
+
+    reap_startup_orphans = reap_orphans_on_startup
+
+    def reset(self) -> None:
+        """Сбрасывает состояние менеджера жизненного цикла (для тестов)."""
+        with self._lock:
+            self.shutdown_requested.clear()
+            self.drain_started.clear()
+            self.drain_completed.clear()
+            self.state = DrainState.READY
+            self.last_signal = None
+            self._drain_thread = None
+
+    reset_state = reset
+    reset_for_tests = reset
+
diff --git a/core/turn_session_manager.py b/core/turn_session_manager.py
new file mode 100644
index 0000000..489ea04
--- /dev/null
+++ b/core/turn_session_manager.py
@@ -0,0 +1,1754 @@
+"""Менеджер отвязанных сессий хода и кольцевой буфер событий (ADR-0005 / AD-001).
+
+Модуль отделяет жизненный цикл выполнения хода (`ManagedTurn`) от жизненного цикла
+клиентского HTTP/SSE-соединения:
+- При разрыве клиентского сокета ход переходит из `RUNNING_ATTACHED` в `RUNNING_DETACHED`
+  и продолжает чтение вывода дочернего CLI в фоновом потоке до терминального состояния.
+- Детерминированный `turn_key` дедуплицирует только активные (нетерминальные) ходы;
+  повторный запрос с тем же промптом после терминального состояния запускает новый ход
+  с новым `turn_id` (поддержка Regenerate, RW-003).
+- Кольцевой буфер `TurnBuffer` ограничен `MAX_TURN_TEXT_BYTES = 10 МиБ` на ход и
+  `MAX_TURN_BUFFER_TOTAL_BYTES = 128 МиБ` / `MAX_BUFFERED_TURNS = 128` глобально.
+- При вытеснении событий из кольцевого буфера запрос дочитки с устаревшим курсором
+  (`from_seq < oldest_available_seq - 1`) порождает `GapDetectedError` для ответа
+  `HTTP 410 Gone` (`code="GAP_DETECTED"`, RW-006).
+- Модуль не импортирует `core.tool_emulation`, `http.server` или `adapters.*` (FU-003).
+"""
+
+from __future__ import annotations
+
+from collections import deque
+from collections.abc import Callable, Iterator
+from dataclasses import asdict, dataclass, field
+import hashlib
+import hmac
+import json
+import os
+from pathlib import Path
+import queue
+import re
+import signal
+import tempfile
+import threading
+import time
+from typing import Any
+import uuid
+
+from core.backend_adapter import ToolCall, TurnResult, Usage
+from core.watchdog import (
+    FINISH_RESERVE_S,
+    IDLE_TIMEOUT_S,
+    SAFETY_CAP_S,
+    WATCHDOG_INTERVAL_S,
+    AdaptiveTimeoutController,
+    ProcessWatchdog,
+)
+
+SNAPSHOT_SCHEMA_VERSION = "1.0"
+TURN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
+
+KNOWN_EVENT_KINDS = frozenset(
+    {"reasoning", "content", "tool_call", "error", "done", "status"}
+)
+
+MAX_TURN_TEXT_BYTES: int = 10 * 1024 * 1024
+MAX_BUFFERED_TURNS: int = 128
+MAX_TURN_BUFFER_TOTAL_BYTES: int = 128 * 1024 * 1024
+TURN_RETENTION_S: float = 3600.0
+CANCEL_SIGTERM_GRACE_S: float = 2.0
+
+STATE_QUEUED = "QUEUED"
+STATE_RUNNING_ATTACHED = "RUNNING_ATTACHED"
+STATE_RUNNING_DETACHED = "RUNNING_DETACHED"
+STATE_COMPLETED = "COMPLETED"
+STATE_CANCELLED = "CANCELLED"
+STATE_FAILED_BACKEND = "FAILED_BACKEND"
+STATE_TIMED_OUT_IDLE = "TIMED_OUT_IDLE"
+STATE_TIMED_OUT_CAP = "TIMED_OUT_CAP"
+STATE_INTERRUPTED_DRAIN = "INTERRUPTED_DRAIN"
+
+ACTIVE_TURN_STATES = frozenset(
+    {STATE_QUEUED, STATE_RUNNING_ATTACHED, STATE_RUNNING_DETACHED}
+)
+TERMINAL_TURN_STATES = frozenset(
+    {
+        STATE_COMPLETED,
+        STATE_CANCELLED,
+        STATE_FAILED_BACKEND,
+        STATE_TIMED_OUT_IDLE,
+        STATE_TIMED_OUT_CAP,
+        STATE_INTERRUPTED_DRAIN,
+    }
+)
+
+_SECRET_PATTERNS = (
+    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
+    re.compile(
+        r"(?i)((?:DROID_DSH_BRIDGE_KEY|FACTORY_API_KEY|META_API_KEY|API_KEY|TOKEN|SECRET)\s*[=:]\s*)([^\s\"',;]+)"
+    ),
+    re.compile(r"\b(?:fk|sk)-[A-Za-z0-9_-]{10,}\b"),
+)
+
+
+def validate_turn_id(turn_id: Any) -> bool:
+    """Проверяет идентификатор хода по строгому шаблону `^[a-zA-Z0-9_-]{1,64}$`."""
+    return isinstance(turn_id, str) and bool(TURN_ID_RE.fullmatch(turn_id))
+
+
+def hash_owner_token(token_or_peer: str | None) -> str:
+    """Вычисляет SHA-256 хеш токена владельца или локального пира для изоляции хода."""
+    raw = (token_or_peer or "anonymous").strip()
+    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
+
+
+hash_token = hash_owner_token
+
+
+def _is_detached_enabled() -> bool:
+    """Проверяет флаг включения фонового доведения ходов (`BRIDGE_DETACHED_TURNS_ENABLED` / `DSH_BRIDGE_DETACHED_ENABLED`)."""
+    val = os.environ.get(
+        "BRIDGE_DETACHED_TURNS_ENABLED",
+        os.environ.get(
+            "BRIDGE_ENABLE_DETACHED_TURNS",
+            os.environ.get("DSH_BRIDGE_DETACHED_ENABLED", "true"),
+        ),
+    )
+    return str(val).strip().lower() not in ("0", "false", "no", "off")
+
+
+def _is_watchdog_enabled() -> bool:
+    """Проверяет флаг включения адаптивного watchdog (`BRIDGE_ADAPTIVE_WATCHDOG_ENABLED` / `DSH_BRIDGE_WATCHDOG_ENABLED`)."""
+    val = os.environ.get(
+        "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED",
+        os.environ.get(
+            "BRIDGE_ENABLE_ADAPTIVE_WATCHDOG",
+            os.environ.get("DSH_BRIDGE_WATCHDOG_ENABLED", "true"),
+        ),
+    )
+    return str(val).strip().lower() not in ("0", "false", "no", "off")
+
+
+def _is_drain_enabled() -> bool:
+    """Проверяет флаг включения неблокирующего drain (`BRIDGE_DRAIN_ON_SHUTDOWN` / `DSH_BRIDGE_DRAIN_ENABLED`)."""
+    val = os.environ.get(
+        "BRIDGE_DRAIN_ON_SHUTDOWN",
+        os.environ.get(
+            "BRIDGE_ENABLE_GRACEFUL_DRAIN",
+            os.environ.get("DSH_BRIDGE_DRAIN_ENABLED", "true"),
+        ),
+    )
+    return str(val).strip().lower() not in ("0", "false", "no", "off")
+
+
+
+def verify_bearer_token(provided: str | None, expected: str | None) -> bool:
+    """Константная по времени сверка Bearer-токена (`hmac.compare_digest`)."""
+    if not expected:
+        return True
+    if not provided or not isinstance(provided, str):
+        return False
+    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
+
+
+def mask_secrets(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
+    """Маскирует секреты и ключи авторизации перед записью снапшота на диск."""
+    if not text:
+        return ""
+    masked = text
+    for pat in _SECRET_PATTERNS:
+        if pat.groups >= 2:
+            masked = pat.sub(r"\1[REDACTED]", masked)
+        else:
+            masked = pat.sub("[REDACTED]", masked)
+    for env_key in ("DROID_DSH_BRIDGE_KEY", "FACTORY_API_KEY", "META_API_KEY"):
+        env_val = os.environ.get(env_key)
+        if env_val and len(env_val) >= 6 and env_val in masked:
+            masked = masked.replace(env_val, "[REDACTED]")
+    for sec in extra_secrets:
+        if sec and len(sec) >= 6 and sec in masked:
+            masked = masked.replace(sec, "[REDACTED]")
+    return masked
+
+
+def compute_turn_key(
+    cwd: str | None,
+    model: str,
+    session_id: str | None,
+    messages: list[dict[str, Any]] | tuple[Any, ...],
+    default_workspace: str = "",
+) -> str:
+    """Детерминированный `turn_key` по спецификации §4.1 (включая последнее сообщение)."""
+    raw_cwd = (cwd or default_workspace or "").strip() or "."
+    norm_cwd = os.path.normpath(raw_cwd)
+    norm_model = (model or "").strip()
+    norm_session = (session_id or "").strip()
+    messages_canonical = json.dumps(
+        list(messages) if messages is not None else [],
+        sort_keys=True,
+        separators=(",", ":"),
+        ensure_ascii=False,
+    )
+    messages_sha256 = hashlib.sha256(messages_canonical.encode("utf-8")).hexdigest()
+    outer = json.dumps(
+        [norm_cwd, norm_model, norm_session, messages_sha256],
+        separators=(",", ":"),
+        ensure_ascii=False,
+    )
+    return hashlib.sha256(outer.encode("utf-8")).hexdigest()
+
+
+class TurnNotFoundError(KeyError):
+    """Запрошенный `turn_id` не найден в памяти и на диске (`HTTP 404`)."""
+
+
+class TurnForbiddenError(PermissionError):
+    """Попытка доступа к чужому ходу (`owner_token_hash` не совпадает, `HTTP 403`)."""
+
+
+class InvalidTurnIdError(ValueError):
+    """Некорректный формат `turn_id` (`HTTP 400`)."""
+
+
+class GapDetectedError(Exception):
+    """Запрошенный курсор `from_seq` вытеснен из кольцевого буфера 10 МиБ (`HTTP 410`)."""
+
+    def __init__(
+        self,
+        *,
+        turn_id: str,
+        requested_from_seq: int,
+        oldest_available_seq: int,
+        last_seq: int,
+        snapshot_url: str = "",
+        state_dump_path: str = "",
+    ) -> None:
+        super().__init__(
+            f"GAP_DETECTED turn_id={turn_id} requested_from_seq={requested_from_seq} "
+            f"oldest_available_seq={oldest_available_seq} last_seq={last_seq}"
+        )
+        self.turn_id = turn_id
+        self.requested_from_seq = int(requested_from_seq)
+        self.oldest_available_seq = int(oldest_available_seq)
+        self.last_seq = int(last_seq)
+        self.snapshot_url = snapshot_url or f"/v1/turns/{turn_id}"
+        self.state_dump_path = (
+            state_dump_path or f"workspace/state/turns/{turn_id}.json"
+        )
+
+    def to_http_payload(self) -> dict[str, Any]:
+        """Формирует JSON-ответ для `HTTP 410 Gone` по контракту §3.1 (RW-006)."""
+        return {
+            "error": {
+                "message": (
+                    "Requested sequence has been evicted from the 10 MiB ring buffer; "
+                    f"fetch full state snapshot via GET /v1/turns/{self.turn_id}"
+                ),
+                "type": "stream_gap_error",
+                "code": "GAP_DETECTED",
+                "turn_id": self.turn_id,
+                "requested_from_seq": self.requested_from_seq,
+                "oldest_available_seq": self.oldest_available_seq,
+                "last_seq": self.last_seq,
+                "snapshot_url": self.snapshot_url,
+                "state_dump_path": self.state_dump_path,
+            }
+        }
+
+
+@dataclass(frozen=True)
+class BufferedTurnEvent:
+    """Событие хода в кольцевом буфере `TurnBuffer` с монотонным `seq`."""
+
+    seq: int
+    ts: float
+    kind: str
+    payload: Any
+    byte_len: int
+
+    def to_sse_frame(
+        self,
+        *,
+        completion_id: str = "",
+        created: int = 0,
+        model: str = "",
+    ) -> str:
+        """Форматирует событие в SSE-кадр с заголовком `id: <seq>`."""
+        cid = completion_id or f"chatcmpl-turn-{self.seq}"
+        ts_created = created or int(self.ts)
+        if self.kind in ("content", "reasoning"):
+            field_name = "content" if self.kind == "content" else "reasoning_content"
+            text_val = (
+                self.payload
+                if isinstance(self.payload, str)
+                else str(self.payload or "")
+            )
+            data = json.dumps(
+                {
+                    "id": cid,
+                    "object": "chat.completion.chunk",
+                    "created": ts_created,
+                    "model": model,
+                    "choices": [
+                        {
+                            "index": 0,
+                            "delta": {field_name: text_val},
+                            "finish_reason": None,
+                        }
+                    ],
+                },
+                ensure_ascii=False,
+            )
+            return f"id: {self.seq}\ndata: {data}\n\n"
+        if self.kind == "tool_call":
+            call_dict = (
+                self.payload
+                if isinstance(self.payload, dict)
+                else asdict(self.payload)
+                if hasattr(self.payload, "__dataclass_fields__")
+                else {"function": {"name": "unknown", "arguments": str(self.payload)}}
+            )
+            data = json.dumps(
+                {
+                    "id": cid,
+                    "object": "chat.completion.chunk",
+                    "created": ts_created,
+                    "model": model,
+                    "choices": [
+                        {
+                            "index": 0,
+                            "delta": {"tool_calls": [call_dict]},
+                            "finish_reason": None,
+                        }
+                    ],
+                },
+                ensure_ascii=False,
+            )
+            return f"id: {self.seq}\ndata: {data}\n\n"
+        if self.kind == "error":
+            err_obj = (
+                self.payload
+                if isinstance(self.payload, dict)
+                else {"message": str(self.payload), "type": "stream_error"}
+            )
+            data = json.dumps(
+                {
+                    "id": cid,
+                    "object": "chat.completion.chunk",
+                    "created": ts_created,
+                    "model": model,
+                    "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
+                    "error": err_obj,
+                },
+                ensure_ascii=False,
+            )
+            return f"id: {self.seq}\ndata: {data}\n\n"
+        if self.kind == "done":
+            finish = "stop"
+            usage_payload = None
+            if isinstance(self.payload, dict):
+                finish = str(self.payload.get("finish_reason") or "stop")
+                usage_payload = self.payload.get("usage")
+            chunk_obj: dict[str, Any] = {
+                "id": cid,
+                "object": "chat.completion.chunk",
+                "created": ts_created,
+                "model": model,
+                "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
+            }
+            if usage_payload:
+                chunk_obj["usage"] = usage_payload
+            data = json.dumps(chunk_obj, ensure_ascii=False)
+            return f"id: {self.seq}\ndata: {data}\n\ndata: [DONE]\n\n"
+        # Расширяемый passthrough для status и неизвестных будущих типов событий (FU-002).
+        raw_data = json.dumps(
+            self.payload
+            if isinstance(self.payload, (dict, list, str, int, float, bool))
+            or self.payload is None
+            else str(self.payload),
+            ensure_ascii=False,
+        )
+        return f"event: {self.kind}\nid: {self.seq}\ndata: {raw_data}\n\n"
+
+
+class StreamSubscriber:
+    """Подписчик живого SSE-потока с неблокирующей очередью доставки."""
+
+    def __init__(self, subscriber_id: str | None = None, maxsize: int = 4096) -> None:
+        self.subscriber_id = subscriber_id or uuid.uuid4().hex[:12]
+        self.queue: queue.Queue[BufferedTurnEvent | None] = queue.Queue(maxsize=maxsize)
+        self.closed = False
+
+    def publish(self, event: BufferedTurnEvent | None) -> bool:
+        if self.closed:
+            return False
+        try:
+            self.queue.put_nowait(event)
+            return True
+        except queue.Full:
+            self.closed = True
+            return False
+
+    def close(self) -> None:
+        self.closed = True
+        try:
+            self.queue.put_nowait(None)
+        except queue.Full:
+            pass
+
+
+class TurnBuffer:
+    """Кольцевой буфер событий одного хода с лимитом `MAX_TURN_TEXT_BYTES` (10 МиБ)."""
+
+    def __init__(self, max_bytes: int = MAX_TURN_TEXT_BYTES) -> None:
+        self.max_bytes = max(1, int(max_bytes))
+        self._lock = threading.RLock()
+        self._events: deque[BufferedTurnEvent] = deque()
+        self.oldest_available_seq: int = 1
+        self.last_seq: int = 0
+        self.total_bytes: int = 0
+        self.evicted_bytes: int = 0
+        self.evicted_count: int = 0
+        self.sealed: bool = False
+
+        self._reasoning_chunks: deque[str] = deque()
+        self._reasoning_bytes: int = 0
+        self._content_chunks: deque[str] = deque()
+        self._content_bytes: int = 0
+        self.tool_calls: list[dict[str, Any]] = []
+        self.usage: dict[str, int] = {
+            "prompt_tokens": 0,
+            "completion_tokens": 0,
+            "total_tokens": 0,
+        }
+        self.error: dict[str, Any] | None = None
+        self._subscribers: dict[str, StreamSubscriber] = {}
+
+    @staticmethod
+    def _estimate_bytes(kind: str, payload: Any) -> int:
+        if isinstance(payload, str):
+            return max(1, len(payload.encode("utf-8", errors="replace")))
+        try:
+            encoded = json.dumps(payload, ensure_ascii=False).encode(
+                "utf-8", errors="replace"
+            )
+            return max(1, len(encoded))
+        except Exception:  # noqa: BLE001
+            return max(1, len(str(payload).encode("utf-8", errors="replace")))
+
+    def _append_bounded_text(
+        self, chunks: deque[str], current_bytes: int, piece: str
+    ) -> int:
+        if not piece:
+            return current_bytes
+        piece_bytes = len(piece.encode("utf-8", errors="replace"))
+        if piece_bytes > self.max_bytes:
+            piece = piece.encode("utf-8", errors="replace")[-self.max_bytes :].decode(
+                "utf-8", errors="ignore"
+            )
+            piece_bytes = len(piece.encode("utf-8", errors="replace"))
+        chunks.append(piece)
+        current_bytes += piece_bytes
+        while current_bytes > self.max_bytes and len(chunks) > 1:
+            removed = chunks.popleft()
+            current_bytes -= len(removed.encode("utf-8", errors="replace"))
+        return max(0, current_bytes)
+
+    def append(self, kind: str, payload: Any) -> BufferedTurnEvent:
+        """Добавляет событие в буфер, вытесняя старые записи при превышении `max_bytes`."""
+        with self._lock:
+            if self.sealed:
+                raise RuntimeError("TurnBuffer is already sealed")
+            self.last_seq += 1
+            seq = self.last_seq
+            byte_len = self._estimate_bytes(kind, payload)
+            event = BufferedTurnEvent(
+                seq=seq,
+                ts=time.time(),
+                kind=str(kind),
+                payload=payload,
+                byte_len=byte_len,
+            )
+            self._events.append(event)
+            self.total_bytes += byte_len
+
+            if kind == "reasoning" and isinstance(payload, str):
+                self._reasoning_bytes = self._append_bounded_text(
+                    self._reasoning_chunks, self._reasoning_bytes, payload
+                )
+            elif kind == "content" and isinstance(payload, str):
+                self._content_bytes = self._append_bounded_text(
+                    self._content_chunks, self._content_bytes, payload
+                )
+            elif kind == "tool_call":
+                call_dict = (
+                    dict(payload)
+                    if isinstance(payload, dict)
+                    else asdict(payload)
+                    if hasattr(payload, "__dataclass_fields__")
+                    else {"function": {"name": "unknown", "arguments": str(payload)}}
+                )
+                self.tool_calls.append(call_dict)
+            elif kind == "error":
+                self.error = (
+                    dict(payload)
+                    if isinstance(payload, dict)
+                    else {"message": str(payload), "type": "stream_error"}
+                )
+            elif kind == "done" and isinstance(payload, dict):
+                raw_usage = payload.get("usage")
+                if isinstance(raw_usage, dict):
+                    self.set_usage(raw_usage)
+
+            # Вытеснение старых событий при превышении кольцевого лимита (RW-006).
+            while self.total_bytes > self.max_bytes and self._events:
+                evicted = self._events.popleft()
+                self.total_bytes = max(0, self.total_bytes - evicted.byte_len)
+                self.evicted_bytes += evicted.byte_len
+                self.evicted_count += 1
+
+            if self._events:
+                self.oldest_available_seq = self._events[0].seq
+            else:
+                self.oldest_available_seq = self.last_seq + 1
+
+            subscribers = list(self._subscribers.values())
+
+        for sub in subscribers:
+            sub.publish(event)
+        return event
+
+    def set_usage(self, usage: Usage | dict[str, Any]) -> None:
+        """Обновляет счётчики токенов хода."""
+        with self._lock:
+            if isinstance(usage, Usage):
+                in_tok = int(usage.input_tokens or 0)
+                out_tok = int(usage.output_tokens or 0)
+                cache_tok = usage.cache_read_tokens
+            elif isinstance(usage, dict):
+                in_tok = int(
+                    usage.get("prompt_tokens")
+                    or usage.get("input_tokens")
+                    or 0
+                )
+                out_tok = int(
+                    usage.get("completion_tokens")
+                    or usage.get("output_tokens")
+                    or 0
+                )
+                cache_tok = usage.get("cache_read_tokens")
+            else:
+                return
+            self.usage = {
+                "prompt_tokens": in_tok,
+                "completion_tokens": out_tok,
+                "total_tokens": in_tok + out_tok,
+            }
+            if cache_tok is not None:
+                self.usage["cache_read_tokens"] = int(cache_tok)
+
+    def get_reasoning_text(self) -> str:
+        with self._lock:
+            return "".join(self._reasoning_chunks)
+
+    def get_content_text(self) -> str:
+        with self._lock:
+            return "".join(self._content_chunks)
+
+    def seal(self) -> None:
+        """Запечатывает буфер при переходе хода в терминальное состояние."""
+        with self._lock:
+            if self.sealed:
+                return
+            self.sealed = True
+            subscribers = list(self._subscribers.values())
+            self._subscribers.clear()
+        for sub in subscribers:
+            sub.close()
+
+    def clear_ring_memory(self) -> int:
+        """Освобождает кольцевой список событий в памяти после сброса снапшота на диск."""
+        with self._lock:
+            freed = self.total_bytes
+            self._events.clear()
+            self.total_bytes = 0
+            return freed
+
+    def check_gap(
+        self,
+        from_seq: int,
+        *,
+        turn_id: str = "",
+        state_dump_path: str = "",
+    ) -> None:
+        """Проверяет, не вытеснено ли событие `from_seq + 1` из кольцевого буфера."""
+        with self._lock:
+            req_seq = max(0, int(from_seq))
+            if self.oldest_available_seq > 1 and req_seq < self.oldest_available_seq - 1:
+                raise GapDetectedError(
+                    turn_id=turn_id,
+                    requested_from_seq=req_seq,
+                    oldest_available_seq=self.oldest_available_seq,
+                    last_seq=self.last_seq,
+                    snapshot_url=f"/v1/turns/{turn_id}",
+                    state_dump_path=state_dump_path
+                    or f"workspace/state/turns/{turn_id}.json",
+                )
+
+    def events_since(
+        self,
+        from_seq: int = 0,
+        *,
+        turn_id: str = "",
+        state_dump_path: str = "",
+    ) -> list[BufferedTurnEvent]:
+        """Возвращает события с `seq > from_seq` или выбрасывает `GapDetectedError` (410)."""
+        with self._lock:
+            self.check_gap(
+                from_seq, turn_id=turn_id, state_dump_path=state_dump_path
+            )
+            req_seq = max(0, int(from_seq))
+            return [ev for ev in self._events if ev.seq > req_seq]
+
+    get_since = events_since
+
+    def subscribe(
+        self,
+        from_seq: int = 0,
+        *,
+        turn_id: str = "",
+        state_dump_path: str = "",
+    ) -> tuple[list[BufferedTurnEvent], StreamSubscriber | None]:
+        """Атомарно проверяет gap, возвращает backlog `seq > from_seq` и регистрирует подписчика."""
+        with self._lock:
+            self.check_gap(
+                from_seq, turn_id=turn_id, state_dump_path=state_dump_path
+            )
+            req_seq = max(0, int(from_seq))
+            backlog = [ev for ev in self._events if ev.seq > req_seq]
+            if self.sealed:
+                return backlog, None
+            sub = StreamSubscriber()
+            self._subscribers[sub.subscriber_id] = sub
+            return backlog, sub
+
+    def unsubscribe(self, subscriber: StreamSubscriber | None) -> None:
+        if subscriber is None:
+            return
+        subscriber.close()
+        with self._lock:
+            self._subscribers.pop(subscriber.subscriber_id, None)
+
+    def active_subscriber_count(self) -> int:
+        with self._lock:
+            return len(self._subscribers)
+
+
+@dataclass
+class ManagedTurn:
+    """Дескриптор управляемого хода в `TurnSessionManager`."""
+
+    turn_id: str
+    turn_key: str
+    rid: str
+    model: str
+    backend: str
+    cwd: str
+    owner_token_hash: str
+    stream: bool = True
+    emulate_tools: bool = False
+    status: str = STATE_QUEUED
+    created_at: float = field(default_factory=time.time)
+    updated_at: float = field(default_factory=time.time)
+    started_monotonic: float = field(default_factory=time.monotonic)
+    pgid: int | None = None
+    command_name: str = ""
+    buffer: TurnBuffer = field(default_factory=TurnBuffer)
+    timeout_controller: AdaptiveTimeoutController | None = None
+    cancel_event: threading.Event = field(default_factory=threading.Event)
+    done_event: threading.Event = field(default_factory=threading.Event)
+    result: TurnResult | None = None
+    final_dict: dict[str, Any] | None = None
+    state_dump_path: str = ""
+    _slot_release_fn: Callable[[], None] | None = None
+    _slot_released: bool = False
+    _cancel_callbacks: list[Callable[[], None]] = field(default_factory=list)
+    _lock: threading.RLock = field(default_factory=threading.RLock)
+
+    @property
+    def is_terminal(self) -> bool:
+        with self._lock:
+            return self.status in TERMINAL_TURN_STATES
+
+    @property
+    def is_active(self) -> bool:
+        with self._lock:
+            return self.status in ACTIVE_TURN_STATES
+
+    def add_cancel_callback(self, cb: Callable[[], None]) -> None:
+        with self._lock:
+            self._cancel_callbacks.append(cb)
+
+    def mark_detached(self) -> None:
+        """Переводит ход в состояние `RUNNING_DETACHED` при разрыве клиентского сокета."""
+        with self._lock:
+            if self.status == STATE_RUNNING_ATTACHED:
+                self.status = STATE_RUNNING_DETACHED
+                self.updated_at = time.time()
+
+    def touch_activity(self, kind: str = "protocol") -> None:
+        """Обновляет метку активности хода и сбрасывает таймер простоя."""
+        if kind == "detached":
+            self.mark_detached()
+            return
+        with self._lock:
+            self.updated_at = time.time()
+            ctrl = self.timeout_controller
+        if ctrl is not None:
+            ctrl.record_activity(kind or "protocol")
+
+    def bind_process(
+        self,
+        *,
+        pgid: int | None = None,
+        terminate_fn: Callable[[], None] | None = None,
+    ) -> None:
+        """Привязывает PGID или callback прерывания к активному ходу."""
+        with self._lock:
+            if isinstance(pgid, int) and pgid > 0:
+                self.pgid = pgid
+                if self.timeout_controller is not None:
+                    self.timeout_controller.register_pgid(pgid)
+            if terminate_fn is not None and terminate_fn not in self._cancel_callbacks:
+                self._cancel_callbacks.append(terminate_fn)
+
+    def release_slot_once(self) -> bool:
+        """Идемпотентно освобождает семафор конкурентности ровно один раз."""
+        with self._lock:
+            if self._slot_released:
+                return False
+            self._slot_released = True
+            fn = self._slot_release_fn
+            self._slot_release_fn = None
+        if fn is not None:
+            try:
+                fn()
+            except Exception:  # noqa: BLE001
+                pass
+            return True
+        return False
+
+    def to_snapshot_dict(self, *, scrub_secrets: bool = True) -> dict[str, Any]:
+        """Формирует словарь состояния версии `1.0` для `GET /v1/turns/<turn_id>` и диска."""
+        with self._lock:
+            reasoning = self.buffer.get_reasoning_text()
+            content = self.buffer.get_content_text()
+            if not content and self.result is not None and self.result.text:
+                content = self.result.text
+            if not reasoning and self.result is not None and self.result.reasoning:
+                reasoning = self.result.reasoning
+            if scrub_secrets:
+                reasoning = mask_secrets(reasoning)
+                content = mask_secrets(content)
+            err_obj = self.buffer.error
+            if err_obj is not None and scrub_secrets:
+                err_obj = {
+                    k: mask_secrets(v) if isinstance(v, str) else v
+                    for k, v in err_obj.items()
+                }
+            tool_calls = list(self.buffer.tool_calls)
+            if not tool_calls and self.result is not None and self.result.tool_calls:
+                tool_calls = [asdict(tc) for tc in self.result.tool_calls]
+            return {
+                "schema_version": SNAPSHOT_SCHEMA_VERSION,
+                "turn_id": self.turn_id,
+                "turn_key": self.turn_key,
+                "rid": self.rid,
+                "model": self.model,
+                "backend": self.backend,
+                "status": self.status.lower(),
+                "state": self.status,
+                "created_at": self.created_at,
+                "updated_at": self.updated_at,
+                "oldest_available_seq": self.buffer.oldest_available_seq,
+                "last_seq": self.buffer.last_seq,
+                "reasoning_content": reasoning,
+                "content": content,
+                "tool_calls": tool_calls,
+                "usage": dict(self.buffer.usage),
+                "error": err_obj,
+                "owner_token_hash": self.owner_token_hash,
+            }
+
+
+def _atomic_write_json_0600(path: Path, payload: Any) -> None:
+    """Атомарно записывает JSON-файл с правами `0600` в каталог с правами `0700`."""
+    parent = path.parent
+    parent.mkdir(parents=True, exist_ok=True)
+    try:
+        parent.chmod(0o700)
+    except OSError:
+        pass
+    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
+    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
+    tmp_path = Path(tmp_name)
+    try:
+        try:
+            os.fchmod(fd, 0o600)
+        except (AttributeError, OSError):
+            pass
+        with os.fdopen(fd, "wb") as fh:
+            fh.write(raw)
+            fh.flush()
+            os.fsync(fh.fileno())
+        os.chmod(tmp_path, 0o600)
+        os.replace(tmp_path, path)
+        os.chmod(path, 0o600)
+    except BaseException:
+        try:
+            tmp_path.unlink(missing_ok=True)
+        except OSError:
+            pass
+        raise
+
+
+class TurnSessionManager:
+    """Реестр и оркестратор отвязанных ходов (`ManagedTurn`) для всех адаптеров хаба."""
+
+    def __init__(
+        self,
+        workspace: Path | str | Callable[[], Path] | None = None,
+        *,
+        state_root: Path | str | Callable[[], Path] | None = None,
+        max_concurrent: int | None = None,
+        max_turn_bytes: int = MAX_TURN_TEXT_BYTES,
+        max_buffered_turns: int = MAX_BUFFERED_TURNS,
+        max_total_buffer_bytes: int = MAX_TURN_BUFFER_TOTAL_BYTES,
+        turn_retention_s: float = TURN_RETENTION_S,
+        idle_timeout_s: float = IDLE_TIMEOUT_S,
+        safety_cap_s: float = SAFETY_CAP_S,
+        finish_reserve_s: float = FINISH_RESERVE_S,
+        watchdog_interval_s: float = WATCHDOG_INTERVAL_S,
+        cancel_grace_s: float = CANCEL_SIGTERM_GRACE_S,
+        detached_enabled_fn: Callable[[], bool] | None = None,
+        watchdog_enabled_fn: Callable[[], bool] | None = None,
+        finalize_fn: Callable[[TurnResult, bool], TurnResult] | None = None,
+        log_fn: Callable[[str], None] | None = None,
+        clock: Callable[[], float] = time.monotonic,
+        persist_children_file: bool = True,
+    ) -> None:
+        ws_source = workspace if workspace is not None else (state_root or ".")
+        self._workspace_fn: Callable[[], Path] = (
+            (lambda: Path(ws_source))
+            if isinstance(ws_source, (str, Path))
+            else ws_source
+        )
+        self._state_root_fn: Callable[[], Path] | None = (
+            None
+            if state_root is None
+            else (
+                (lambda: Path(state_root))
+                if isinstance(state_root, (str, Path))
+                else state_root
+            )
+        )
+        self.max_concurrent = int(max_concurrent or 32)
+        self.max_turn_bytes = int(max_turn_bytes)
+        self.max_buffered_turns = int(max_buffered_turns)
+        self.max_total_buffer_bytes = int(max_total_buffer_bytes)
+        self.turn_retention_s = float(turn_retention_s)
+        self.idle_timeout_s = float(idle_timeout_s)
+        self.safety_cap_s = float(safety_cap_s)
+        self.finish_reserve_s = float(finish_reserve_s)
+        self.watchdog_interval_s = float(watchdog_interval_s)
+        self.cancel_grace_s = float(cancel_grace_s)
+        self.persist_children_file = bool(persist_children_file)
+        self._detached_enabled_fn = detached_enabled_fn or _is_detached_enabled
+        self._watchdog_enabled_fn = watchdog_enabled_fn or _is_watchdog_enabled
+        self._finalize_fn = finalize_fn
+
+        self._log_fn = log_fn
+        self._clock = clock
+
+        self._lock = threading.RLock()
+        self._cond = threading.Condition(self._lock)
+        self._turns_by_id: dict[str, ManagedTurn] = {}
+        self._active_by_key: dict[str, str] = {}
+        self._children: dict[int, dict[str, Any]] = {}
+
+    @property
+    def workspace(self) -> Path:
+        return Path(self._workspace_fn())
+
+    @property
+    def state_dir(self) -> Path:
+        if self._state_root_fn is not None:
+            sr = Path(self._state_root_fn())
+            return sr.parent if sr.name == "turns" else sr
+        ws = self.workspace
+        if ws.name == "state":
+            return ws
+        if ws.name == "turns":
+            return ws.parent
+        return ws / "state"
+
+    @property
+    def turns_dir(self) -> Path:
+        if self._state_root_fn is not None:
+            sr = Path(self._state_root_fn())
+            return sr if sr.name == "turns" else sr / "turns"
+        ws = self.workspace
+        if ws.name == "turns":
+            return ws
+        return self.state_dir / "turns"
+
+    @property
+    def children_path(self) -> Path:
+        return self.state_dir / "children.json"
+
+    def is_detached_enabled(self) -> bool:
+        return bool(self._detached_enabled_fn())
+
+    def is_watchdog_enabled(self) -> bool:
+        return bool(self._watchdog_enabled_fn())
+
+    def _log(self, message: str) -> None:
+        if self._log_fn is not None:
+            try:
+                self._log_fn(message)
+            except Exception:  # noqa: BLE001
+                pass
+
+    def ensure_state_dirs(self) -> None:
+        """Создаёт каталоги `workspace/state` и `workspace/state/turns` с правами `0700`."""
+        for directory in (self.state_dir, self.turns_dir):
+            directory.mkdir(parents=True, exist_ok=True)
+            try:
+                directory.chmod(0o700)
+            except OSError:
+                pass
+
+    def register_child_pgid(
+        self,
+        turn_id_or_pgid: str | int,
+        pgid: int | None = None,
+        *,
+        pid: int | None = None,
+        rid: str = "",
+        command: str = "muse",
+        backend: str = "",
+        turn_id: str = "",
+    ) -> None:
+        """Регистрирует `pgid` дочернего процесса в `ManagedTurn` и `children.json`."""
+        if isinstance(turn_id_or_pgid, int):
+            actual_pgid = turn_id_or_pgid
+            actual_turn_id = turn_id
+        else:
+            actual_turn_id = str(turn_id_or_pgid)
+            actual_pgid = int(pgid or 0)
+        cmd_name = backend or command or "muse"
+        if not isinstance(actual_pgid, int) or actual_pgid <= 0:
+            return
+        with self._lock:
+            turn = self._turns_by_id.get(actual_turn_id) if actual_turn_id else None
+            if turn is not None:
+                turn.pgid = actual_pgid
+                turn.command_name = cmd_name
+                if turn.timeout_controller is not None:
+                    turn.timeout_controller.register_pgid(actual_pgid)
+            self._children[actual_pgid] = {
+                "pid": int(pid or actual_pgid),
+                "pgid": int(actual_pgid),
+                "turn_id": actual_turn_id,
+                "rid": rid or (turn.rid if turn else ""),
+                "started_at": time.time(),
+                "command": cmd_name,
+            }
+            if self.persist_children_file:
+                self._persist_children_locked()
+
+    def unregister_child_pgid(self, pgid: int | None) -> None:
+        """Удаляет `pgid` из реестра `children.json` после подтверждённой гибели группы."""
+        if not isinstance(pgid, int) or pgid <= 0:
+            return
+        with self._lock:
+            if pgid in self._children:
+                self._children.pop(pgid, None)
+                if self.persist_children_file:
+                    self._persist_children_locked()
+
+    def _persist_children_locked(self) -> None:
+        try:
+            self.ensure_state_dirs()
+            payload = {
+                "schema_version": SNAPSHOT_SCHEMA_VERSION,
+                "children": list(self._children.values()),
+            }
+            _atomic_write_json_0600(self.children_path, payload)
+        except OSError:
+            pass
+
+    def persist_turn_snapshot(self, turn: ManagedTurn) -> Path | None:
+        """Сохраняет снапшот хода в `workspace/state/turns/<turn_id>.json` с правами `0600`."""
+        try:
+            self.ensure_state_dirs()
+            path = self.turns_dir / f"{turn.turn_id}.json"
+            snapshot = turn.to_snapshot_dict(scrub_secrets=True)
+            _atomic_write_json_0600(path, snapshot)
+            turn.state_dump_path = str(path)
+            return path
+        except OSError as exc:
+            self._log(
+                f"turn_snapshot_write_failed turn_id={turn.turn_id} err={exc.__class__.__name__}"
+            )
+            return None
+
+    def _enforce_memory_caps_locked(self) -> None:
+        """Вытесняет старые терминальные ходы из RAM на диск при превышении лимитов."""
+        now = time.time()
+        expired_ids = [
+            tid
+            for tid, t in self._turns_by_id.items()
+            if t.is_terminal and (now - t.updated_at) >= self.turn_retention_s
+        ]
+        for tid in expired_ids:
+            turn = self._turns_by_id.pop(tid, None)
+            if turn is not None:
+                self.persist_turn_snapshot(turn)
+                turn.buffer.clear_ring_memory()
+
+        terminal_turns = sorted(
+            (t for t in self._turns_by_id.values() if t.is_terminal),
+            key=lambda item: item.updated_at,
+        )
+        while len(self._turns_by_id) > self.max_buffered_turns and terminal_turns:
+            oldest = terminal_turns.pop(0)
+            self.persist_turn_snapshot(oldest)
+            oldest.buffer.clear_ring_memory()
+            self._turns_by_id.pop(oldest.turn_id, None)
+
+        total_ram = sum(t.buffer.total_bytes for t in self._turns_by_id.values())
+        if total_ram > self.max_total_buffer_bytes:
+            for oldest in terminal_turns:
+                if total_ram <= self.max_total_buffer_bytes:
+                    break
+                if oldest.buffer.total_bytes > 0:
+                    self.persist_turn_snapshot(oldest)
+                    total_ram -= oldest.buffer.clear_ring_memory()
+
+    def sweep_expired_snapshots(self) -> int:
+        """Удаляет снапшоты на диске старше `TURN_RETENTION_S`."""
+        removed = 0
+        cutoff = time.time() - self.turn_retention_s
+        try:
+            if not self.turns_dir.exists():
+                return 0
+            for path in self.turns_dir.glob("*.json"):
+                try:
+                    if path.stat().st_mtime < cutoff:
+                        path.unlink(missing_ok=True)
+                        removed += 1
+                except OSError:
+                    pass
+        except OSError:
+            pass
+        return removed
+
+    def active_turns(self) -> list[ManagedTurn]:
+        """Возвращает список всех нетерминальных ходов."""
+        with self._lock:
+            return [t for t in self._turns_by_id.values() if t.is_active]
+
+    def active_count(self) -> int:
+        """Количество активных (нетерминальных) ходов в менеджере."""
+        with self._lock:
+            return sum(1 for t in self._turns_by_id.values() if t.is_active)
+
+    def find_active_by_key(
+        self, turn_key: str, owner_token_hash: str | None = None
+    ) -> ManagedTurn | None:
+        """Находит активный ход по `turn_key` (терминальные ходы игнорируются, RW-003)."""
+        with self._lock:
+            tid = self._active_by_key.get(turn_key)
+            if not tid:
+                return None
+            turn = self._turns_by_id.get(tid)
+            if turn is None or not turn.is_active:
+                self._active_by_key.pop(turn_key, None)
+                return None
+            if (
+                owner_token_hash is not None
+                and turn.owner_token_hash
+                and turn.owner_token_hash != owner_token_hash
+            ):
+                return None
+            return turn
+
+    def get_turn(
+        self,
+        turn_id: str,
+        *,
+        owner_token_hash: str | None = None,
+    ) -> ManagedTurn:
+        """Возвращает `ManagedTurn` по `turn_id` с проверкой формата и владельца."""
+        if not validate_turn_id(turn_id):
+            raise InvalidTurnIdError(f"Invalid turn_id: {turn_id!r}")
+        with self._lock:
+            turn = self._turns_by_id.get(turn_id)
+        if turn is None:
+            raise TurnNotFoundError(turn_id)
+        if (
+            owner_token_hash is not None
+            and turn.owner_token_hash
+            and turn.owner_token_hash != owner_token_hash
+        ):
+            raise TurnForbiddenError(turn_id)
+        return turn
+
+    def get_turn_snapshot(
+        self,
+        turn_id: str,
+        *,
+        owner_token_hash: str | None = None,
+    ) -> dict[str, Any]:
+        """Возвращает снапшот хода из памяти или с диска (`workspace/state/turns/<id>.json`)."""
+        if not validate_turn_id(turn_id):
+            raise InvalidTurnIdError(f"Invalid turn_id: {turn_id!r}")
+        with self._lock:
+            turn = self._turns_by_id.get(turn_id)
+        if turn is not None:
+            if (
+                owner_token_hash is not None
+                and turn.owner_token_hash
+                and turn.owner_token_hash != owner_token_hash
+            ):
+                raise TurnForbiddenError(turn_id)
+            return turn.to_snapshot_dict(scrub_secrets=True)
+
+        disk_path = self.turns_dir / f"{turn_id}.json"
+        if not disk_path.is_file():
+            raise TurnNotFoundError(turn_id)
+        try:
+            data = json.loads(disk_path.read_text(encoding="utf-8"))
+        except (OSError, json.JSONDecodeError) as exc:
+            raise TurnNotFoundError(turn_id) from exc
+        saved_owner = data.get("owner_token_hash")
+        if (
+            owner_token_hash is not None
+            and saved_owner
+            and saved_owner != owner_token_hash
+        ):
+            raise TurnForbiddenError(turn_id)
+        return data
+
+    def create_or_attach_turn(
+        self,
+        *,
+        model: str,
+        backend: str,
+        cwd: str,
+        messages: list[dict[str, Any]] | tuple[Any, ...],
+        session_id: str | None = None,
+        owner_token_hash: str = "",
+        rid: str = "",
+        requested_turn_id: str | None = None,
+        resume_turn_id: str | None = None,
+        stream: bool = True,
+        emulate_tools: bool = False,
+        idle_timeout_s: float | None = None,
+        safety_cap_s: float | None = None,
+        slot_release_fn: Callable[[], None] | None = None,
+    ) -> tuple[ManagedTurn, bool]:
+        """Создаёт новый `ManagedTurn` или подключается к уже идущему активному ходу.
+
+        Возвращает `(turn, is_existing_active)`.
+        Терминальные ходы с тем же `turn_key` никогда не переиспользуются без явного
+        `resume_turn_id`, чтобы кнопка Regenerate всегда создавала новый ход (RW-003).
+        """
+        if resume_turn_id is not None and resume_turn_id != "":
+            if not validate_turn_id(resume_turn_id):
+                raise InvalidTurnIdError(f"Invalid X-Turn-Resume-Id: {resume_turn_id!r}")
+            existing = self.get_turn(
+                resume_turn_id, owner_token_hash=owner_token_hash or None
+            )
+            with self._lock:
+                if existing.status == STATE_RUNNING_DETACHED:
+                    existing.status = STATE_RUNNING_ATTACHED
+                    existing.updated_at = time.time()
+            return existing, True
+
+        if requested_turn_id is not None and requested_turn_id != "":
+            if not validate_turn_id(requested_turn_id):
+                raise InvalidTurnIdError(f"Invalid X-Turn-Id: {requested_turn_id!r}")
+
+        turn_key = compute_turn_key(
+            cwd=cwd,
+            model=model,
+            session_id=session_id,
+            messages=messages,
+            default_workspace=str(self.workspace),
+        )
+
+        with self._lock:
+            if requested_turn_id and requested_turn_id in self._turns_by_id:
+                existing_by_id = self._turns_by_id[requested_turn_id]
+                if (
+                    owner_token_hash
+                    and existing_by_id.owner_token_hash
+                    and existing_by_id.owner_token_hash != owner_token_hash
+                ):
+                    raise TurnForbiddenError(requested_turn_id)
+                if existing_by_id.is_active:
+                    if existing_by_id.status == STATE_RUNNING_DETACHED:
+                        existing_by_id.status = STATE_RUNNING_ATTACHED
+                        existing_by_id.updated_at = time.time()
+                    return existing_by_id, True
+
+            active_tid = self._active_by_key.get(turn_key)
+            if active_tid:
+                active_turn = self._turns_by_id.get(active_tid)
+                if active_turn is not None and active_turn.is_active:
+                    if (
+                        active_turn.status == STATE_RUNNING_DETACHED
+                        and (
+                            not owner_token_hash
+                            or not active_turn.owner_token_hash
+                            or active_turn.owner_token_hash == owner_token_hash
+                        )
+                    ):
+                        active_turn.status = STATE_RUNNING_ATTACHED
+                        active_turn.updated_at = time.time()
+                        self._log(
+                            f"turn_reattached rid={rid or active_turn.rid} "
+                            f"turn_id={active_turn.turn_id} turn_key={turn_key[:12]}"
+                        )
+                        return active_turn, True
+                else:
+                    self._active_by_key.pop(turn_key, None)
+
+            turn_id = (
+                requested_turn_id
+                if (
+                    requested_turn_id
+                    and requested_turn_id not in self._turns_by_id
+                )
+                else f"turn_{uuid.uuid4().hex[:16]}"
+            )
+            eff_rid = rid or f"r-{uuid.uuid4().hex[:8]}"
+            eff_idle = (
+                float(idle_timeout_s)
+                if idle_timeout_s is not None
+                else self.idle_timeout_s
+            )
+            eff_cap = (
+                float(safety_cap_s)
+                if safety_cap_s is not None
+                else self.safety_cap_s
+            )
+            controller = AdaptiveTimeoutController(
+                idle_timeout_s=eff_idle,
+                safety_cap_s=eff_cap,
+                finish_reserve_s=self.finish_reserve_s,
+                watchdog_enabled=self.is_watchdog_enabled(),
+                clock=self._clock,
+                rid=eff_rid,
+                turn_id=turn_id,
+                log_fn=self._log_fn,
+            )
+            dump_path = str(self.turns_dir / f"{turn_id}.json")
+            turn = ManagedTurn(
+                turn_id=turn_id,
+                turn_key=turn_key,
+                rid=eff_rid,
+                model=model,
+                backend=backend,
+                cwd=cwd,
+                owner_token_hash=owner_token_hash,
+                stream=stream,
+                emulate_tools=emulate_tools,
+                status=STATE_RUNNING_ATTACHED,
+                buffer=TurnBuffer(max_bytes=self.max_turn_bytes),
+                timeout_controller=controller,
+                state_dump_path=dump_path,
+                _slot_release_fn=slot_release_fn,
+            )
+            self._turns_by_id[turn_id] = turn
+            self._active_by_key[turn_key] = turn_id
+            self._enforce_memory_caps_locked()
+            return turn, False
+
+    def finalize_abandoned_turn(self, turn: ManagedTurn | None) -> None:
+        """Гарантирует освобождение ресурсов хода при выходе потока-исполнителя до финализации."""
+        if turn is None:
+            return
+        turn.release_slot_once()
+        with self._lock:
+            if turn.is_terminal:
+                return
+            turn.status = STATE_CANCELLED
+            turn.updated_at = time.time()
+            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
+                self._active_by_key.pop(turn.turn_key, None)
+            if not turn.buffer.sealed:
+                turn.buffer.seal()
+            if turn.timeout_controller is not None:
+                turn.timeout_controller.close()
+            turn.done_event.set()
+            self._cond.notify_all()
+
+    def mark_detached(self, turn_id: str) -> None:
+        """Переводит активный ход в `RUNNING_DETACHED` при разрыве HTTP-соединения."""
+        with self._lock:
+            turn = self._turns_by_id.get(turn_id)
+            if turn is not None and turn.status == STATE_RUNNING_ATTACHED:
+                turn.status = STATE_RUNNING_DETACHED
+                turn.updated_at = time.time()
+                self._log(
+                    f"turn_detached rid={turn.rid} turn_id={turn.turn_id} "
+                    f"last_seq={turn.buffer.last_seq}"
+                )
+
+    def _terminate_pgid(self, pgid: int | None, grace_s: float) -> None:
+        if not isinstance(pgid, int) or pgid <= 0:
+            return
+        try:
+            os.killpg(pgid, signal.SIGTERM)
+        except (ProcessLookupError, PermissionError, OSError):
+            self.unregister_child_pgid(pgid)
+            return
+        deadline = time.monotonic() + max(0.05, grace_s)
+        while time.monotonic() < deadline:
+            if not ProcessWatchdog.is_group_alive(pgid):
+                self.unregister_child_pgid(pgid)
+                return
+            time.sleep(0.05)
+        try:
+            os.killpg(pgid, signal.SIGKILL)
+        except (ProcessLookupError, PermissionError, OSError):
+            pass
+        self.unregister_child_pgid(pgid)
+
+    def cancel_turn(
+        self,
+        turn_id: str,
+        *,
+        owner_token_hash: str | None = None,
+        reason: str = "client_cancelled",
+    ) -> ManagedTurn:
+        """Явно отменяет ход (`SIGTERM -> 2s -> SIGKILL`), немедленно освобождая слот (RW-001)."""
+        turn = self.get_turn(turn_id, owner_token_hash=owner_token_hash)
+        with self._lock:
+            if turn.status == STATE_CANCELLED:
+                return turn
+            if turn.is_terminal:
+                return turn
+            turn.status = STATE_CANCELLED
+            turn.updated_at = time.time()
+            turn.cancel_event.set()
+            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
+                self._active_by_key.pop(turn.turn_key, None)
+            pgid = turn.pgid
+            callbacks = list(turn._cancel_callbacks)
+
+        # Немедленно возвращаем слот MAX_CONCURRENT до ожидания завершения потомка.
+        turn.release_slot_once()
+
+        for cb in callbacks:
+            try:
+                cb()
+            except Exception:  # noqa: BLE001
+                pass
+
+        if pgid is not None:
+            self._terminate_pgid(pgid, self.cancel_grace_s)
+
+        with self._lock:
+            if not turn.buffer.sealed:
+                turn.buffer.append(
+                    "error",
+                    {
+                        "message": f"Turn cancelled ({reason})",
+                        "type": "cancelled",
+                        "code": "turn_cancelled",
+                    },
+                )
+                turn.buffer.seal()
+            if turn.timeout_controller is not None:
+                turn.timeout_controller.close()
+            turn.done_event.set()
+            self.persist_turn_snapshot(turn)
+            self._cond.notify_all()
+        self._log(f"turn_cancelled rid={turn.rid} turn_id={turn.turn_id} reason={reason}")
+        return turn
+
+    def interrupt_for_drain(
+        self, turn: ManagedTurn, message: str = "bridge restart drain timeout exceeded"
+    ) -> None:
+        """Завершает ход при истечении `DRAIN_TIMEOUT_S` со сбросом reasoning и error-чанком."""
+        with self._lock:
+            if turn.is_terminal:
+                return
+            turn.status = STATE_INTERRUPTED_DRAIN
+            turn.updated_at = time.time()
+            turn.cancel_event.set()
+            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
+                self._active_by_key.pop(turn.turn_key, None)
+            pgid = turn.pgid
+            callbacks = list(turn._cancel_callbacks)
+
+        turn.release_slot_once()
+        for cb in callbacks:
+            try:
+                cb()
+            except Exception:  # noqa: BLE001
+                pass
+        if pgid is not None:
+            self._terminate_pgid(pgid, self.cancel_grace_s)
+
+        with self._lock:
+            if not turn.buffer.sealed:
+                turn.buffer.append(
+                    "error",
+                    {
+                        "message": message,
+                        "type": "overloaded",
+                        "code": "drain_timeout",
+                    },
+                )
+                turn.buffer.seal()
+            if turn.timeout_controller is not None:
+                turn.timeout_controller.close()
+            turn.done_event.set()
+            self.persist_turn_snapshot(turn)
+            self._cond.notify_all()
+
+    def complete_turn_from_result(
+        self,
+        turn: ManagedTurn,
+        raw_result: TurnResult,
+        *,
+        backend_kind: str = "",
+    ) -> dict[str, Any]:
+        """Финализирует `ManagedTurn` по `TurnResult` от `BackendAdapter.execute_turn`."""
+        final_res = (
+            self._finalize_fn(raw_result, turn.emulate_tools)
+            if self._finalize_fn is not None
+            else raw_result
+        )
+        turn.release_slot_once()
+
+        with self._lock:
+            if turn.status in (STATE_CANCELLED, STATE_INTERRUPTED_DRAIN):
+                if turn.final_dict is not None:
+                    return turn.final_dict
+                return {
+                    "state": "client_gone",
+                    "rc": 1,
+                    "text": turn.buffer.get_content_text(),
+                    "err": "cancelled",
+                    "usage": dict(turn.buffer.usage),
+                    "result": {},
+                    "tool_calls": list(turn.buffer.tool_calls),
+                    "events": [],
+                    "backend_kind": backend_kind or turn.backend,
+                    "turn_id": turn.turn_id,
+                }
+
+            turn.result = final_res
+            turn.buffer.set_usage(final_res.usage)
+
+            # Если адаптер не стримил события живьём, докладываем их в TurnBuffer.
+            had_content = bool(turn.buffer.get_content_text())
+            had_reasoning = bool(turn.buffer.get_reasoning_text())
+            had_tool_calls = bool(turn.buffer.tool_calls)
+            if not turn.buffer.sealed:
+                for ev in final_res.events or ():
+                    if ev.kind == "reasoning" and isinstance(ev.value, str):
+                        if not had_reasoning:
+                            turn.buffer.append("reasoning", ev.value)
+                    elif ev.kind == "content" and isinstance(ev.value, str):
+                        if not had_content:
+                            turn.buffer.append("content", ev.value)
+                    elif ev.kind == "tool_call" and not had_tool_calls:
+                        call_val = (
+                            asdict(ev.value)
+                            if isinstance(ev.value, ToolCall)
+                            else ev.value
+                        )
+                        turn.buffer.append("tool_call", call_val)
+                if not final_res.events:
+                    if final_res.reasoning and not had_reasoning:
+                        turn.buffer.append("reasoning", final_res.reasoning)
+                    if final_res.text and not had_content:
+                        turn.buffer.append("content", final_res.text)
+                    if not had_tool_calls:
+                        for tc in final_res.tool_calls or ():
+                            turn.buffer.append("tool_call", asdict(tc))
+
+            res_state = str(final_res.state or "done")
+            term_reason = (
+                turn.timeout_controller.terminated_reason
+                if turn.timeout_controller is not None
+                else ""
+            )
+            if term_reason == "idle_timeout" or res_state == "idle_timeout":
+                turn.status = STATE_TIMED_OUT_IDLE
+            elif term_reason == "absolute_cap" or res_state in (
+                "timeout",
+                "safety_cap",
+            ):
+                turn.status = STATE_TIMED_OUT_CAP
+            elif res_state == "done" and int(final_res.rc or 0) == 0:
+                turn.status = STATE_COMPLETED
+            elif res_state == "client_gone":
+                turn.status = STATE_CANCELLED
+            else:
+                turn.status = STATE_FAILED_BACKEND
+
+            if not turn.buffer.sealed:
+                if turn.status == STATE_COMPLETED:
+                    finish_reason = (
+                        "tool_calls" if final_res.tool_calls else "stop"
+                    )
+                    turn.buffer.append(
+                        "done",
+                        {
+                            "finish_reason": finish_reason,
+                            "usage": dict(turn.buffer.usage),
+                        },
+                    )
+                else:
+                    turn.buffer.append(
+                        "error",
+                        {
+                            "message": str(final_res.err or res_state),
+                            "type": (
+                                "timeout_error"
+                                if turn.status
+                                in (STATE_TIMED_OUT_IDLE, STATE_TIMED_OUT_CAP)
+                                else "proxy_error"
+                            ),
+                            "code": turn.status.lower(),
+                        },
+                    )
+                turn.buffer.seal()
+
+            turn.updated_at = time.time()
+            if self._active_by_key.get(turn.turn_key) == turn.turn_id:
+                self._active_by_key.pop(turn.turn_key, None)
+            if turn.pgid is not None:
+                self.unregister_child_pgid(turn.pgid)
+            if turn.timeout_controller is not None:
+                turn.timeout_controller.close()
+
+            out = {
+                "state": (
+                    "timeout"
+                    if turn.status in (STATE_TIMED_OUT_IDLE, STATE_TIMED_OUT_CAP)
+                    else final_res.state
+                ),
+                "rc": final_res.rc,
+                "text": final_res.text,
+                "err": final_res.err,
+                "usage": asdict(final_res.usage),
+                "result": {},
+                "tool_calls": [asdict(call) for call in final_res.tool_calls],
+                "events": [
+                    (
+                        event.kind,
+                        asdict(event.value)
+                        if not isinstance(event.value, str)
+                        else event.value,
+                    )
+                    for event in final_res.events or ()
+                ],
+                "backend_kind": backend_kind or turn.backend,
+                "turn_id": turn.turn_id,
+                "turn_status": turn.status,
+            }
+            turn.final_dict = out
+            turn.done_event.set()
+            self.persist_turn_snapshot(turn)
+            self._enforce_memory_caps_locked()
+            self._cond.notify_all()
+            return out
+
+    def spawn_detached_execution(
+        self,
+        turn: ManagedTurn,
+        runner_fn: Callable[[ManagedTurn], TurnResult],
+        *,
+        backend_kind: str = "",
+    ) -> threading.Thread:
+        """Запускает выполнение хода в отдельном daemon-потоке, отвязанном от HTTP-хендлера."""
+
+        def _worker() -> None:
+            watchdog_stop = threading.Event()
+
+            def _watchdog_loop() -> None:
+                while not watchdog_stop.wait(self.watchdog_interval_s):
+                    if turn.is_terminal or turn.cancel_event.is_set():
+                        return
+                    ctrl = turn.timeout_controller
+                    if ctrl is None:
+                        continue
+                    should_stop, reason, _metrics = ctrl.check(turn.pgid)
+                    if should_stop and reason in ("idle_timeout", "absolute_cap"):
+                        self._log(
+                            f"watchdog_triggered rid={turn.rid} turn_id={turn.turn_id} "
+                            f"reason={reason} pgid={turn.pgid}"
+                        )
+                        turn.cancel_event.set()
+                        if turn.pgid is not None:
+                            self._terminate_pgid(turn.pgid, self.cancel_grace_s)
+                        return
+
+            wd_thread: threading.Thread | None = None
+            if self.is_watchdog_enabled() and turn.timeout_controller is not None:
+                wd_thread = threading.Thread(
+                    target=_watchdog_loop,
+                    name=f"turn-wd-{turn.turn_id}",
+                    daemon=True,
+                )
+                wd_thread.start()
+
+            try:
+                raw_res = runner_fn(turn)
+                if (
+                    turn.timeout_controller is not None
+                    and turn.timeout_controller.terminated_reason
+                    in ("idle_timeout", "absolute_cap")
+                ):
+                    reason = turn.timeout_controller.terminated_reason
+                    raw_res = TurnResult(
+                        state=(
+                            "idle_timeout"
+                            if reason == "idle_timeout"
+                            else "timeout"
+                        ),
+                        rc=124,
+                        text=raw_res.text,
+                        reasoning=raw_res.reasoning,
+                        usage=raw_res.usage,
+                        err=f"Turn terminated by watchdog: {reason}",
+                        events=raw_res.events,
+                        tool_calls=raw_res.tool_calls,
+                    )
+                self.complete_turn_from_result(
+                    turn, raw_res, backend_kind=backend_kind
+                )
+            except Exception as exc:  # noqa: BLE001
+                err_res = TurnResult(
+                    state="backend_error",
+                    rc=1,
+                    err=f"{exc.__class__.__name__}: {exc}",
+                )
+                self.complete_turn_from_result(
+                    turn, err_res, backend_kind=backend_kind
+                )
+            finally:
+                watchdog_stop.set()
+
+        worker = threading.Thread(
+            target=_worker,
+            name=f"turn-exec-{turn.turn_id}",
+            daemon=True,
+        )
+        worker.start()
+        return worker
+
+    def wait_for_active_turns(self, timeout: float) -> list[ManagedTurn]:
+        """Ожидает завершения всех активных ходов до `timeout` секунд.
+
+        Возвращает список ходов, оставшихся активными после истечения `timeout`.
+        """
+        deadline = time.monotonic() + max(0.0, float(timeout))
+        with self._cond:
+            while True:
+                remaining_turns = [
+                    t for t in self._turns_by_id.values() if t.is_active
+                ]
+                if not remaining_turns:
+                    return []
+                wait_s = deadline - time.monotonic()
+                if wait_s <= 0:
+                    return remaining_turns
+                self._cond.wait(timeout=min(wait_s, 0.25))
+
+    def iter_sse_stream(
+        self,
+        turn: ManagedTurn,
+        *,
+        from_seq: int = 0,
+        keepalive_interval_s: float = 10.0,
+        client_gone_fn: Callable[[], bool] | None = None,
+    ) -> Iterator[str]:
+        """Генерирует SSE-поток событий хода (`id: <seq>\\ndata: ...\\n\\n`) с поддержкой дочитки."""
+        backlog, subscriber = turn.buffer.subscribe(
+            from_seq=from_seq,
+            turn_id=turn.turn_id,
+            state_dump_path=turn.state_dump_path,
+        )
+        completion_id = f"chatcmpl-turn-{turn.turn_id}"
+        created = int(turn.created_at)
+        try:
+            for ev in backlog:
+                yield ev.to_sse_frame(
+                    completion_id=completion_id,
+                    created=created,
+                    model=turn.model,
+                )
+            if subscriber is None:
+                return
+            while True:
+                if client_gone_fn is not None and client_gone_fn():
+                    self.mark_detached(turn.turn_id)
+                    return
+                try:
+                    ev = subscriber.queue.get(
+                        timeout=max(0.05, float(keepalive_interval_s))
+                    )
+                except queue.Empty:
+                    if client_gone_fn is not None and client_gone_fn():
+                        self.mark_detached(turn.turn_id)
+                        return
+                    if turn.is_terminal:
+                        return
+                    yield ": keepalive\n\n"
+                    continue
+                if ev is None:
+                    return
+                yield ev.to_sse_frame(
+                    completion_id=completion_id,
+                    created=created,
+                    model=turn.model,
+                )
+        finally:
+            turn.buffer.unsubscribe(subscriber)
+
+    def kill_all_active(self) -> None:
+        """Завершает все активные ходы при истечении drain или аварийной остановке."""
+        with self._cond:
+            active = [t for t in self._turns_by_id.values() if t.is_active]
+        for turn in active:
+            try:
+                self.interrupt_for_drain(turn)
+            except Exception:  # noqa: BLE001
+                pass
+
+    def reset(self) -> None:
+        """Сбрасывает состояние менеджера (для изоляции тестов)."""
+        with self._cond:
+            active = [t for t in self._turns_by_id.values() if t.is_active]
+        for turn in active:
+            try:
+                self.cancel_turn(turn.turn_id, reason="reset")
+            except Exception:  # noqa: BLE001
+                pass
+        with self._cond:
+            self._turns_by_id.clear()
+            self._active_by_key.clear()
+            self._children.clear()
+            self._cond.notify_all()
+
+    reset_state = reset
+
diff --git a/core/watchdog.py b/core/watchdog.py
new file mode 100644
index 0000000..78c369b
--- /dev/null
+++ b/core/watchdog.py
@@ -0,0 +1,449 @@
+"""Адаптивный таймер неактивности и мониторинг дерева процессов (ADR-0005 / AD-002).
+
+Модуль реализует двухконтурный контроль времени хода исключительно средствами
+стандартной библиотеки Python на macOS (Darwin):
+1. Контур активности (`IDLE_TIMEOUT_S = 300.0` с): таймер неактивности сбрасывается
+   только при наличии реального прогресса — протокольных событий от CLI (`on_activity`),
+   положительного прироста процессорного времени (`cputime` delta > 0) в группе `pgid`,
+   или появления новых дочерних PID (`new_descendants`). Спящий дочерний процесс
+   без прироста CPU и без новых потомков таймер не сбрасывает (RW-005).
+2. Предохранительный потолок (`SAFETY_CAP_S = 3600.0` с, `FINISH_RESERVE_S = 35.0` с):
+   абсолютный потолок длительности хода независимо от активности.
+
+При деградации/таймауте вызова `ps` применяется политика fail-closed: событие
+фиксируется в логе (`watchdog_ps_degraded`), а `last_activity_ts` не обновляется.
+"""
+
+from __future__ import annotations
+
+from collections.abc import Callable
+from dataclasses import dataclass
+import os
+import re
+import subprocess
+import threading
+import time
+
+IDLE_TIMEOUT_S: float = 300.0
+SAFETY_CAP_S: float = 3600.0
+FINISH_RESERVE_S: float = 35.0
+WATCHDOG_INTERVAL_S: float = 5.0
+PS_TIMEOUT_S: float = 2.0
+
+DEFAULT_IDLE_TIMEOUT_S: float = IDLE_TIMEOUT_S
+DEFAULT_SAFETY_CAP_S: float = SAFETY_CAP_S
+DEFAULT_FINISH_RESERVE_S: float = FINISH_RESERVE_S
+
+
+_PS_LINE_RE = re.compile(
+    r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s*(.*)$"
+)
+
+
+def parse_cputime(raw: str) -> float:
+    """Разбирает поле `cputime` вывода `ps` (`[[dd-]hh:]mm:ss[.xx]`) в секунды."""
+    token = (raw or "").strip()
+    if not token:
+        return 0.0
+    days = 0
+    if "-" in token:
+        day_part, token = token.split("-", 1)
+        try:
+            days = int(day_part)
+        except ValueError:
+            return 0.0
+    parts = token.split(":")
+    try:
+        if len(parts) == 3:
+            hours = int(parts[0])
+            minutes = int(parts[1])
+            seconds = float(parts[2])
+        elif len(parts) == 2:
+            hours = 0
+            minutes = int(parts[0])
+            seconds = float(parts[1])
+        elif len(parts) == 1:
+            hours = 0
+            minutes = 0
+            seconds = float(parts[0])
+        else:
+            return 0.0
+    except ValueError:
+        return 0.0
+    total = ((days * 24 + hours) * 60 + minutes) * 60 + seconds
+    return max(0.0, float(total))
+
+
+@dataclass(frozen=True)
+class WatchdogMetrics:
+    """Снимок состояния процессной группы `pgid` на одном тике `ProcessWatchdog`."""
+
+    pgid: int
+    alive: bool
+    descendant_pids: tuple[int, ...]
+    new_descendants: tuple[int, ...]
+    cpu_time_s: float
+    cpu_delta_s: float
+    ps_degraded: bool = False
+    sample_ts: float = 0.0
+
+    @property
+    def has_progress(self) -> bool:
+        """Есть ли подтверждённый прогресс (новые потомки или прирост CPU > 0)."""
+        if self.ps_degraded or not self.alive:
+            return False
+        return bool(self.new_descendants) or self.cpu_delta_s > 0.0
+
+    has_activity = has_progress
+
+
+class ProcessWatchdog:
+    """Мониторинг процессной группы `pgid` на macOS/POSIX через `os.killpg` и `ps`."""
+
+    def __init__(
+        self,
+        ps_timeout_s: float = PS_TIMEOUT_S,
+        log_fn: Callable[[str], None] | None = None,
+        rid: str = "",
+        turn_id: str = "",
+    ) -> None:
+        self.ps_timeout_s = float(ps_timeout_s)
+        self._log_fn = log_fn
+        self.rid = rid
+        self.turn_id = turn_id
+        self._lock = threading.Lock()
+        self._prev_cpu_by_pgid: dict[int, dict[int, float]] = {}
+        self._seen_descendants_by_pgid: dict[int, set[int]] = {}
+        self._seeded_pgids: set[int] = set()
+
+    def _log(self, msg: str) -> None:
+        if self._log_fn is not None:
+            try:
+                self._log_fn(msg)
+            except Exception:  # noqa: BLE001
+                pass
+
+    @staticmethod
+    def is_group_alive(pgid: int) -> bool:
+        """Проверяет живость процессной группы `os.killpg(pgid, 0)`."""
+        if not isinstance(pgid, int) or pgid <= 0:
+            return False
+        try:
+            os.killpg(pgid, 0)
+        except ProcessLookupError:
+            return False
+        except PermissionError:
+            return True
+        except OSError:
+            return False
+        return True
+
+    def forget(self, pgid: int) -> None:
+        """Очищает накопленное состояние группы после завершения хода."""
+        with self._lock:
+            self._prev_cpu_by_pgid.pop(pgid, None)
+            self._seen_descendants_by_pgid.pop(pgid, None)
+            self._seeded_pgids.discard(pgid)
+
+    def _run_ps(self, pgid: int) -> subprocess.CompletedProcess[str]:
+        return subprocess.run(
+            ["ps", "-o", "pid=,ppid=,pgid=,stat=,cputime=,command=", "-g", str(pgid)],
+            capture_output=True,
+            text=True,
+            timeout=self.ps_timeout_s,
+            check=False,
+        )
+
+    def _parse_ps_output(
+        self, stdout: str, target_pgid: int
+    ) -> tuple[list[int], dict[int, float], bool]:
+        """Возвращает `(descendant_pids, cpu_by_pid, any_non_zombie_in_group)`."""
+        descendants: list[int] = []
+        cpu_by_pid: dict[int, float] = {}
+        any_alive_proc = False
+        for raw_line in (stdout or "").splitlines():
+            line = raw_line.strip()
+            if not line:
+                continue
+            match = _PS_LINE_RE.match(line)
+            if match is None:
+                continue
+            try:
+                pid = int(match.group(1))
+                _ppid = int(match.group(2))
+                pgid_col = int(match.group(3))
+            except ValueError:
+                continue
+            if pgid_col != target_pgid:
+                continue
+            stat = match.group(4) or ""
+            cputime_str = match.group(5) or ""
+            if stat.upper().startswith("Z"):
+                continue
+            any_alive_proc = True
+            cpu_by_pid[pid] = parse_cputime(cputime_str)
+            if pid != target_pgid:
+                descendants.append(pid)
+        descendants.sort()
+        return descendants, cpu_by_pid, any_alive_proc
+
+    def seed(
+        self, pgid: int, *, rid: str = "", turn_id: str = ""
+    ) -> WatchdogMetrics:
+        """Фиксирует базовый срез PID и cputime группы при старте хода без сброса таймера."""
+        metrics = self.sample(pgid, rid=rid, turn_id=turn_id, _seed_only=True)
+        return metrics
+
+    def sample(
+        self,
+        pgid: int,
+        *,
+        rid: str = "",
+        turn_id: str = "",
+        _seed_only: bool = False,
+    ) -> WatchdogMetrics:
+        """Опрашивает группу `pgid` и вычисляет прирост `cputime` и новых потомков."""
+        now = time.monotonic()
+        eff_rid = rid or self.rid or "-"
+        eff_turn = turn_id or self.turn_id or "-"
+        if not self.is_group_alive(pgid):
+            return WatchdogMetrics(
+                pgid=pgid,
+                alive=False,
+                descendant_pids=(),
+                new_descendants=(),
+                cpu_time_s=0.0,
+                cpu_delta_s=0.0,
+                ps_degraded=False,
+                sample_ts=now,
+            )
+
+        try:
+            proc = self._run_ps(pgid)
+        except (subprocess.TimeoutExpired, OSError) as exc:
+            if not self.is_group_alive(pgid):
+                return WatchdogMetrics(
+                    pgid=pgid,
+                    alive=False,
+                    descendant_pids=(),
+                    new_descendants=(),
+                    cpu_time_s=0.0,
+                    cpu_delta_s=0.0,
+                    ps_degraded=False,
+                    sample_ts=now,
+                )
+            self._log(
+                f"watchdog_ps_degraded rid={eff_rid} turn_id={eff_turn} "
+                f"pgid={pgid} reason={exc.__class__.__name__}"
+            )
+            return WatchdogMetrics(
+                pgid=pgid,
+                alive=True,
+                descendant_pids=(),
+                new_descendants=(),
+                cpu_time_s=0.0,
+                cpu_delta_s=0.0,
+                ps_degraded=True,
+                sample_ts=now,
+            )
+
+        if proc.returncode != 0:
+            if not self.is_group_alive(pgid):
+                return WatchdogMetrics(
+                    pgid=pgid,
+                    alive=False,
+                    descendant_pids=(),
+                    new_descendants=(),
+                    cpu_time_s=0.0,
+                    cpu_delta_s=0.0,
+                    ps_degraded=False,
+                    sample_ts=now,
+                )
+            self._log(
+                f"watchdog_ps_degraded rid={eff_rid} turn_id={eff_turn} "
+                f"pgid={pgid} reason=rc_{proc.returncode}"
+            )
+            return WatchdogMetrics(
+                pgid=pgid,
+                alive=True,
+                descendant_pids=(),
+                new_descendants=(),
+                cpu_time_s=0.0,
+                cpu_delta_s=0.0,
+                ps_degraded=True,
+                sample_ts=now,
+            )
+
+        descendants, cpu_s, any_alive = self._parse_ps_output(proc.stdout, pgid)
+        if not any_alive and not self.is_group_alive(pgid):
+            return WatchdogMetrics(
+                pgid=pgid,
+                alive=False,
+                descendant_pids=(),
+                new_descendants=(),
+                cpu_time_s=0.0,
+                cpu_delta_s=0.0,
+                ps_degraded=False,
+                sample_ts=now,
+            )
+
+        with self._lock:
+            prev_cpu = self._prev_cpu_by_pgid.setdefault(pgid, {})
+            seen_desc = self._seen_descendants_by_pgid.setdefault(pgid, set())
+            if _seed_only:
+                for pid, val in cpu_s.items():
+                    prev_cpu[pid] = max(prev_cpu.get(pid, 0.0), val)
+                seen_desc.update(descendants)
+                self._seeded_pgids.add(pgid)
+                total_cpu = sum(cpu_s.values())
+                return WatchdogMetrics(
+                    pgid=pgid,
+                    alive=True,
+                    descendant_pids=tuple(descendants),
+                    new_descendants=(),
+                    cpu_time_s=total_cpu,
+                    cpu_delta_s=0.0,
+                    ps_degraded=False,
+                    sample_ts=now,
+                )
+
+            cpu_delta = sum(
+                max(0.0, val - prev_cpu.get(pid, 0.0)) for pid, val in cpu_s.items()
+            )
+            new_desc = tuple(sorted(set(descendants) - seen_desc))
+            for pid, val in cpu_s.items():
+                prev_cpu[pid] = max(prev_cpu.get(pid, 0.0), val)
+            seen_desc.update(descendants)
+            self._seeded_pgids.add(pgid)
+            total_cpu = sum(cpu_s.values())
+
+        return WatchdogMetrics(
+            pgid=pgid,
+            alive=True,
+            descendant_pids=tuple(descendants),
+            new_descendants=new_desc,
+            cpu_time_s=total_cpu,
+            cpu_delta_s=cpu_delta,
+            ps_degraded=False,
+            sample_ts=now,
+        )
+
+
+class AdaptiveTimeoutController:
+    """Контроллер двухконтурного таймаута хода (`idle_timeout` + `absolute_cap`)."""
+
+    def __init__(
+        self,
+        idle_timeout_s: float = IDLE_TIMEOUT_S,
+        safety_cap_s: float = SAFETY_CAP_S,
+        finish_reserve_s: float = FINISH_RESERVE_S,
+        watchdog: ProcessWatchdog | None = None,
+        watchdog_enabled: bool = True,
+        clock: Callable[[], float] = time.monotonic,
+        rid: str = "",
+        turn_id: str = "",
+        log_fn: Callable[[str], None] | None = None,
+    ) -> None:
+        self.idle_timeout_s = float(idle_timeout_s)
+        self.safety_cap_s = float(safety_cap_s)
+        self.finish_reserve_s = float(finish_reserve_s)
+        self.watchdog_enabled = bool(watchdog_enabled)
+        self._clock = clock
+        self.rid = rid
+        self.turn_id = turn_id
+        self._log_fn = log_fn
+        self.watchdog = watchdog or ProcessWatchdog(
+            log_fn=log_fn, rid=rid, turn_id=turn_id
+        )
+        self._lock = threading.Lock()
+        now = self._clock()
+        self.started_at: float = now
+        self.last_activity_ts: float = now
+        self.last_activity_kind: str = "start"
+        self.pgid: int | None = None
+        self.terminated_reason: str = ""
+
+    def effective_cap_s(self) -> float:
+        """Эффективный бюджет времени до срабатывания `absolute_cap`."""
+        if self.safety_cap_s > self.finish_reserve_s:
+            return self.safety_cap_s - self.finish_reserve_s
+        return max(0.01, self.safety_cap_s)
+
+    def record_activity(self, kind: str = "protocol") -> None:
+        """Сбрасывает таймер простоя при получении протокольного события от бэкенда."""
+        now = self._clock()
+        with self._lock:
+            self.last_activity_ts = now
+            self.last_activity_kind = kind or "protocol"
+
+    def on_activity(self, kind: str = "protocol") -> None:
+        """Синоним `record_activity` для прямой передачи в `TurnContext.on_activity`."""
+        self.record_activity(kind)
+
+    def register_pgid(self, pgid: int) -> None:
+        """Привязывает PGID дочернего процесса и снимает стартовый базовый срез."""
+        if not isinstance(pgid, int) or pgid <= 0:
+            return
+        with self._lock:
+            self.pgid = pgid
+        if self.watchdog_enabled and self.watchdog is not None:
+            self.watchdog.seed(pgid, rid=self.rid, turn_id=self.turn_id)
+
+    def check(
+        self, pgid: int | None = None
+    ) -> tuple[bool, str, WatchdogMetrics | None]:
+        """Проверяет условия завершения хода.
+
+        Возвращает кортеж `(should_stop, reason, metrics)`, где `reason` при
+        `should_stop == True` принимает одно из значений:
+        - `"absolute_cap"` — превышен предохранительный потолок `SAFETY_CAP_S`;
+        - `"idle_timeout"` — превышен порог неактивности `IDLE_TIMEOUT_S`;
+        - `"child_exited"` — процессная группа завершилась.
+        """
+        with self._lock:
+            target_pgid = pgid if pgid is not None else self.pgid
+            started_at = self.started_at
+
+        now = self._clock()
+        if now - started_at >= self.effective_cap_s():
+            with self._lock:
+                self.terminated_reason = "absolute_cap"
+            return True, "absolute_cap", None
+
+        metrics: WatchdogMetrics | None = None
+        if (
+            self.watchdog_enabled
+            and self.watchdog is not None
+            and isinstance(target_pgid, int)
+            and target_pgid > 0
+        ):
+            metrics = self.watchdog.sample(
+                target_pgid, rid=self.rid, turn_id=self.turn_id
+            )
+            if not metrics.alive:
+                with self._lock:
+                    self.terminated_reason = "child_exited"
+                return True, "child_exited", metrics
+            if metrics.has_progress:
+                with self._lock:
+                    self.last_activity_ts = now
+                    self.last_activity_kind = (
+                        "new_descendants"
+                        if metrics.new_descendants
+                        else "cpu_delta"
+                    )
+
+        with self._lock:
+            idle_elapsed = now - self.last_activity_ts
+            if idle_elapsed >= self.idle_timeout_s:
+                self.terminated_reason = "idle_timeout"
+                return True, "idle_timeout", metrics
+
+        return False, "", metrics
+
+    def close(self) -> None:
+        """Освобождает состояние отслеживаемой группы в `ProcessWatchdog`."""
+        with self._lock:
+            pgid = self.pgid
+        if pgid is not None and self.watchdog is not None:
+            self.watchdog.forget(pgid)
diff --git a/docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md b/docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md
new file mode 100644
index 0000000..b6cbc9b
--- /dev/null
+++ b/docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md
@@ -0,0 +1,131 @@
+# 0005 — Сквозная отказоустойчивость общего слоя хаба: автономное доведение ходов (detached turns), адаптивный сторожевой таймер и плавный drain
+
+## Status
+
+Accepted (2026-10-17, ревизия a2 по замечаниям Архитектурного Совета RW-001..RW-010, FU-001..FU-004).
+Формат: MADR-full / ADR-full.
+Задача: `REQ-EYE-33873-RESILIENCE` (`EYE-33873`), Run ID: `dsh-bridge-resilience-20261017`, критичность: `S2`, профиль: `python-aisdlc-gcge`.
+Архитектурный пакет: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json`.
+Спецификация: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`.
+Расширяет: ADR 0001 (`0001-persistent-droid-bridge.md`), ADR 0002 (`0002-multi-binary-hub.md`), ADR 0004 (`0004-muse-live-streaming-all-steps.md`).
+
+## Y-формулировка
+
+В контексте мульти-бинарного хаба консольных агентов `cli-agent-bridge` (`server.py`, `core/`, `adapters/` и `bridges/muse-bridge/server.py`), обслуживающего клиент DeepSeek Harness (Desktop и Web), сталкиваясь с:
+1. потерей многошаговых ходов при кратковременном разрыве клиентского TCP/SSE-соединения (переключение вкладки, сон ноутбука, перезагрузка UI) из-за принудительного вызова `_kill_current_run()` / `_kill_group()` на `client_gone` (`[F-10]`, `[F-12]`, `[F-34]`),
+2. обрывом активных ходов с вызовами инструментов ровно на 1765-й секунде по слепому абсолютному дедлайну (`1800 - 35 с`) при живом и работающем дочернем процессе (`[F-16]`..`[F-25]`),
+3. мгновенным уничтожением активных ходов при перезапуске моста через `launchctl` из-за отсутствия drain-режима и 5-секундного `ExitTimeOut` (`[F-01]`..`[F-09]`),
+4. ошибкой старта сессии в веб-профиле DSH из-за незарегистрированной переменной `{{cwd}}` в `deployment:persona-suffix` (`[F-27]`..`[F-30]`),
+
+мы решили:
+1. Вынести управление жизненным циклом ходов, адаптивными таймаутами, сторожевым мониторингом процессов и плавной остановкой в **общий слой хаба** (`core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` и фасад `server.py`) без зависимости менеджера сессий от `core.tool_emulation`, обеспечив автоматическое разрешение импортов `core.*` в `bridges/muse-bridge/server.py` через `sys.path` bootstrap и `DSH_BRIDGE_ROOT`;
+2. Отвязать выполнение хода модели от клиентского HTTP/SSE-сокета (**Detached Execution**): запретить убийство процесса модели при отсоединении клиента, доводить ход в фоне до естественного терминала, буферизовать поток событий (`kind: str` с passthrough неизвестных событий, SSE `id: <seq>`, `X-Turn-Id`) в кольцевом буфере `10 МиБ` (при вытеснении возвращать `410 Gone` с `GAP_DETECTED` и `X-Oldest-Available-Seq`) и на диске (`schema_version: "1.0"`, права `0600` в каталоге `0700`), а также предоставить явный эндпоинт отмены хода `POST /v1/turns/<turn_id>/cancel` (`DELETE /v1/turns/<turn_id>`) для немедленного гашения группы процессов (`SIGTERM` -> `2 с` -> `SIGKILL`) и освобождения слота семафора `MAX_CONCURRENT=2`;
+3. Заменить слепой абсолютный дедлайн двухуровневым контроллером (**Adaptive Idle Timeout `300 с` + Safety Cap `3600 с` + `ProcessWatchdog`**), сбрасывающим таймер простоя **только** по событиям протокола (`reasoning`, `content`, `toolCall`), по положительному приросту CPU-времени (`cputime` delta в `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>`) или однократно при появлении нового дочернего PID (спящие процессы без прироста CPU таймер не сбрасывают; при сбое/таймауте `ps` действует fail-closed режим);
+4. Реализовать **Graceful Shutdown & Drain** с неблокирующим обработчиком `SIGTERM`/`SIGINT` через `threading.Event` и выделенным фоновым потоком drain (новым запросам — `503 Retry-After: 5`, активным ходам — доведение до конца в окне `ExitTimeOut = 120 с` / `DRAIN_TIMEOUT_S = 110 с`, при таймауте — терминальный SSE error-чанк и `[DONE]`), дополнив старт хаба процедурой **Orphan Reaper** по реестру `children.json` и фичефлагами аварийного отключения (`DSH_BRIDGE_DETACHED_ENABLED`, `DSH_BRIDGE_WATCHDOG_ENABLED`, `DSH_BRIDGE_DRAIN_ENABLED`);
+5. Убрать `{{cwd}}` из секции `deployment:persona-suffix` в `~/.dsh/profiles/web/cordis.patch.yml`, передавая рабочий каталог через `AGENTS.md` и окружение `DSH_CWD`,
+
+чтобы исключить потерю вычислений, блокировку слотов семафора и оборванные стримы во всех бэкендах хаба (`droid`, `muse` и будущих адаптерах), принимая контролируемый расход памяти на буферизацию фоновых ходов (до 10 МиБ на ход, 128 МиБ глобально) и увеличение окна перезапуска `launchd` при наличии активных ходов до 120 секунд.
+
+---
+
+## Context
+
+Расследование системного аналитика (`analysis/bridge-resilience/evidence-ledger.md`, факты `[F-01]`..`[F-34]`) подтвердило следующие факты:
+- **`[F-01]`..`[F-09]`:** `bridges/muse-bridge/server.py` не перехватывает `SIGTERM` (`signal.signal` отсутствует), потоки `ThreadingHTTPServer` помечены `daemon_threads=True`, а `com.user.dsh-muse-bridge.plist` не задаёт `ExitTimeOut` (действует системный дефолт 5 с). В результате `launchctl kickstart -k` (инцидент `18:52:23`, `[F-10]`, `[F-11]`) мгновенно оборвал активный ход `01a14a8e` без записи `done`/`error` и без отправки финального кадра клиенту.
+- **`[F-12]`, `[F-13]`, `[F-34]`:** Каждый запрос в `muse-bridge` порождает отдельную группу процессов `muse serve` (`start_new_session=True`) с `--no-session-log`. При любом разрыве клиентского сокета ход уничтожается, а следующий запрос открывает чистую сессию без сохранения прогресса. При этом в случае гибели самого моста по `SIGKILL` дочерние группы с `start_new_session=True` остаются сиротами.
+- **`[F-16]`..`[F-26]`:** В `ServeRun.read_msg` и `MuseAdapter._run_exec` действовал только абсолютный дедлайн хода (`1800 - 35 = 1765 с`). Три боевых сбоя (`2026-10-16 22:58:26`, `2026-10-17 02:03:36`, `2026-10-17 14:06:27`) убили ходы ровно через 1765 с от старта, хотя дочерний процесс активно выполнял `toolCall` за 8 с, 16 с и 79 с до обрыва (`[F-24]`). Проверка живости ограничивалась `proc.poll()` без анализа CPU/I/O и дочерних PID (`[F-17]`), а записи `tool_item` в логе не имели `rid` запроса (`[F-24]`).
+- **`[F-27]`..`[F-31]`:** В `~/.dsh/profiles/web/cordis.patch.yml:51-55` задан `suffix: Your working directory is {{cwd}}.`, который вызывает ошибку `unknown prompt variable "{{cwd}}" in section "deployment:persona-suffix"; registered variables: provider, model`.
+
+---
+
+## Decision Drivers
+
+- **D1 (Надёжность стрима и сохранность вычислений):** Ход с вызовами инструментов должен доходить до `completion event` при рестарте моста и при временном отключении клиента (`[F-01]`..`[F-03]`, `[F-10]`, `[F-12]`).
+- **D2 (Фоновая автономия хода и управляемая отмена):** Закрытие вкладки или кратковременный обрыв сети не должны убивать процесс модели (`[F-10]`, `[F-12]`, `[F-13]`, `[F-34]`), но явное нажатие Stop клиентом обязано немедленно завершать процессную группу и освобождать слот `MAX_CONCURRENT=2` (`RW-001`).
+- **D3 (Адаптивность и точность таймаутов):** Активно работающий процесс не должен убиваться по слепому таймеру, но спящий процесс без прироста `cputime` не должен бесконечно продлевать `idle_timeout` (`RW-005`, `FU-004`).
+- **D4 (Единообразие и безопасность в общем слое хаба):** Механизмы устойчивости должны жить в `core/` + `server.py` (ADR 0002), защищать эндпоинты `/v1/turns/*` Bearer-авторизацией, валидацией `turn_id` (`^[a-zA-Z0-9_-]{1,64}$`) и правами `0600`/`0700` на дампы (`RW-002`).
+- **D5 (Операционная безопасность, зачистка сирот и kill-switch):** Неблокирующий перехват сигналов (`RW-007`), уборка сирот при старте по `children.json` (`RW-004`), фичефлаги мгновенного отключения (`RW-009`) и чистый старт профиля DSH Web (`REQ-005`).
+
+---
+
+## Considered Options
+
+### Вопрос 1: Где и как реализовать отказоустойчивость, фоновое доведение ходов и адаптивные таймауты?
+
+- **Option A — Точечные патчи внутри каждого адаптера и отдельного `bridges/muse-bridge/server.py`:**
+  - *Минусы:* Тройное дублирование многопоточного кода; расхождение поведения между `droid` и `muse`; нарушение ADR 0002 и директивы владельца №3.
+- **Option B — Реализация в общем слое хаба (`core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` + фасад `server.py`) с переиспользованием в `muse-bridge` через `sys.path` bootstrap (Выбрано):**
+  - *Плюсы:* Единая кодовая база и единые инварианты для всех бэкендов; чистая модульная граница без зависимости `TurnSessionManager` от `core.tool_emulation` (`FU-003`); прозрачный импорт `core.*` в `bridges/muse-bridge/server.py` через автодобавление корня `cli-agent-bridge` в `sys.path` и симлинк/переменную `DSH_BRIDGE_ROOT` (`RW-008`).
+- **Option C — Внешний супервизор очереди и прокси-демон (Out-of-process Redis/SQLite broker):**
+  - *Минусы:* Нарушает базовый инвариант проекта (zero external runtime dependencies, чистый Python stdlib, один процесс-хаб по ADR 0002).
+
+### Вопрос 2: Поведение при разрыве клиентского соединения (`client_gone`), явной отмене и переполнении буфера
+
+- **Option 2A — Немедленное убийство процесса (Status Quo):** *Отклонено:* приводит к потере 20–30 минут работы модели при любом переключении вкладки или сне ноутбука.
+- **Option 2B — Detached Execution с кольцевым/дисковым буфером в `TurnSessionManager`, эндпоинтом отмены `/cancel` и `410 GAP_DETECTED` (Выбрано):**
+  - При отсоединении сокета воркер хода продолжает работу в состоянии `RUNNING_DETACHED`, складывая события в `TurnBuffer` (`10 МиБ` на ход, `128 МиБ` глобально, снимок `workspace/state/turns/<turn_id>.json` со `schema_version: "1.0"` и правами `0600`).
+  - При нажатии пользователем кнопки Stop вызывается `POST /v1/turns/<turn_id>/cancel` (или `DELETE /v1/turns/<turn_id>`), который переводит ход в `CANCELLED`, гасит группу `SIGTERM` -> `2 с` -> `SIGKILL` и немедленно освобождает слот `MAX_CONCURRENT=2` (`RW-001`).
+  - При запросе клиентом `from_seq`, уже вытесненного из 10-мегабайтного кольцевого буфера, возвращается `HTTP 410 Gone` с кодом `GAP_DETECTED`, заголовком `X-Oldest-Available-Seq` и ссылкой на полный снимок состояния (`RW-006`).
+
+### Вопрос 3: Механика таймаутов длительного хода и контроля активности
+
+- **Option 3A — Только увеличенный абсолютный таймаут (3600 с):** *Отклонено:* зависший процесс удерживает слот 60 минут.
+- **Option 3B — Сброс таймера при любом наличии дочернего процесса в `pgid`:** *Отклонено:* спящий потомок (`sleep`, `bash` в ожидании `stdin`) бесконечно сбрасывает `idle_timeout` до 3600 с (`RW-005`).
+- **Option 3C — Адаптивный таймер неактивности (`IDLE_TIMEOUT_S = 300 с`) + `ProcessWatchdog` по приросту `cputime` и протокольным событиям + fail-closed `ps` + `SAFETY_CAP_S = 3600 с` (Выбрано):**
+  - Таймер простоя сбрасывается только при поступлении событий протокола, при положительном приросте CPU-времени (`cputime` delta > 0) в `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>` или однократно в момент порождения нового дочернего PID. При сбое или таймауте `ps` (> `2 с`) действует fail-closed режим (таймер не сбрасывается).
+
+---
+
+## Decision Outcome
+
+Выбрана комбинация **Option B + Option 2B + Option 3C** (решения `AD-001`..`AD-005`, сопоставленные с `REQ-001`..`REQ-005`):
+
+1. **Модуль `core/turn_session_manager.py` (`AD-001`, `REQ-001`):**
+   - Каждый ход получает валидируемый `turn_id` (`^[a-zA-Z0-9_-]{1,64}$`) и детерминированный `turn_key = sha256(canonical_json([workspace, model_id, session_id_or_rid, digest_history_including_last_user_message]))` (`RW-003`). Автоматический re-attach при `POST /v1/chat/completions` без `X-Turn-Resume-Id` выполняется только к активным (нетерминальным) ходам, исключая ложную дедупликацию при перегенерации.
+   - Колбэк `ctx.client_gone` возвращает `True` только при явной отмене хода (`POST /v1/turns/<turn_id>/cancel` / `DELETE /v1/turns/<turn_id>`) или истечении `DRAIN_TIMEOUT_S`, но никогда при разрыве TCP-сокета клиента.
+   - При вызове `POST /v1/turns/<turn_id>/cancel` (или `DELETE /v1/turns/<turn_id>`) статус переходит в `CANCELLED`, группа `pgid` останавливается (`SIGTERM` -> `2 с` -> `SIGKILL`), слот семафора `MAX_CONCURRENT=2` немедленно освобождается, возвращается `200 {"ok": true, "turn_id": turn_id, "status": "cancelled"}` (`RW-001`).
+   - `BufferedTurnEvent` использует открытый `kind: str` (passthrough неизвестных видов событий), SSE-ответы передают заголовок `X-Turn-Id` и поле `id: <seq>` в каждом кадре (`FU-002`), а дисковые снимки `workspace/state/turns/<turn_id>.json` маркируются `"schema_version": "1.0"` и создаются с правами `0600` в каталоге `0700` (`RW-002`, `RW-010`).
+   - При вытеснении запрошенного `from_seq` из кольцевого буфера `10 МиБ` возвращается `HTTP 410 Gone` (`GAP_DETECTED`, `X-Oldest-Available-Seq`) со ссылкой на дамп состояния (`RW-006`).
+   - Эндпоинты `/v1/turns/*` требуют проверки Bearer-токена и совпадения `owner_token_hash` (`RW-002`).
+
+2. **Модуль `core/watchdog.py` (`AD-002`, `REQ-002`):**
+   - `IDLE_TIMEOUT_S = 300 с` + `SAFETY_CAP_S = 3600 с` (с `FINISH_RESERVE_S = 35 с`).
+   - `ProcessWatchdog` каждые `5 с` вызывает `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>` (таймаут `2.0 с`) и сбрасывает `idle_timeout` только при приросте `cputime` (`cpu_delta > 0`), при появлении нового дочернего PID или при событиях протокола (`RW-005`). Спящие процессы без прироста CPU таймер не сбрасывают; при ошибке/таймауте `ps` действует fail-closed режим (`FU-004`).
+   - Все записи лога маркируются `rid=<id> turn_id=<id> pgid=<pgid>` с кодами причин `idle_timeout`, `absolute_cap`, `child_exited`, `drain_timeout`, `cancelled`.
+
+3. **Общий слой хаба и поставка `core.*` (`AD-003`, `REQ-003`):**
+   - Модули `core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` не зависят от `core.tool_emulation` (`FU-003`) и единообразно обслуживают `DroidAdapter` и `MuseAdapter`.
+   - `bridges/muse-bridge/server.py` автоматически добавляет корень `cli-agent-bridge` в `sys.path` на старте (с поддержкой `DSH_BRIDGE_ROOT` и симлинка `core`), гарантируя доступность `core.*` в изолированном процессе (`RW-008`).
+
+4. **Модуль `core/lifecycle.py`: Orphan Reaper, Неблокирующий Drain и Kill-Switch (`AD-004`, `REQ-004`):**
+   - На старте хаба `HubLifecycleManager.reap_orphans_on_startup()` читает `workspace/state/children.json`, проверяет живые PID через `os.kill(pid, 0)` + имя команды в `ps` и уничтожает осиротевшие группы от упавших предыдущих инстансов (`SIGTERM` -> `SIGKILL`) (`RW-004`).
+   - Обработчик `SIGTERM`/`SIGINT` в главном потоке только выставляет `threading.Event` (`shutdown_requested`) без захвата замков (`RW-007`). Процедура drain (`DRAIN_TIMEOUT_S = 110 с` при `ExitTimeOut = 120 с` в `launchd` plist) и `server.shutdown()` выполняется в выделенном фоновом потоке.
+   - Фичефлаги `DSH_BRIDGE_DETACHED_ENABLED`, `DSH_BRIDGE_WATCHDOG_ENABLED`, `DSH_BRIDGE_DRAIN_ENABLED` (по умолчанию `true`) позволяют оперативно отключить любой из новых механизмов без отката кода (`RW-009`).
+
+5. **Исправление профиля DSH (`AD-005`, `REQ-005`):**
+   - Из секции `deployment:persona-suffix` в `~/.dsh/profiles/web/cordis.patch.yml` удаляется `suffix: Your working directory is {{cwd}}.`. Контекст рабочей директории передаётся через `AGENTS.md` проекта и переменную окружения `DSH_CWD`.
+
+---
+
+## Pros and Cons of the Consequences
+
+### Положительные последствия (Pros)
+- **Нулевая потеря ходов и мгновенное освобождение слотов по Stop (QS-2, RW-001):** Разрыв сети не убивает ход, а нажатие Stop в UI вызывает `/v1/turns/<id>/cancel` и сразу освобождает слот `MAX_CONCURRENT=2`.
+- **Точное детектирование как живых инструментов, так и зависших `sleep`-процессов (QS-3, RW-005):** Активные инструменты работают до `3600 с`, а спящие без CPU процессы и зависания прерываются за `300 с`.
+- **Защита от сирот, дедлоков сигналов и уязвимостей доступа (RW-002, RW-004, RW-007):** Неблокирующий сигнальный цикл исключает дедлок в `serve_forever`, orphan reaper очищает зависшие группы при рестарте после `SIGKILL`, а `turn_id` regex + Bearer auth + `0600` защищают данные ходов.
+- **Безопасный роллаут с kill-switch (RW-009):** Любую из трёх подсистем можно отключить переменной окружения за секунды.
+
+### Отрицательные последствия и риски (Cons & Mitigations)
+- **Вытеснение ранних чанков при ответе > 10 МиБ:** *Митигация:* честный ответ `410 Gone` (`GAP_DETECTED`, `X-Oldest-Available-Seq`) со ссылкой на полный агрегированный снимок `GET /v1/turns/<turn_id>` (`RW-006`).
+- **Задержка рестарта сервиса при активном ходе:** *Митигация:* новые запросы сразу получают `503 Retry-After: 5`, а по истечении 110 с гарантирован чистый выход до прихода `SIGKILL` от `launchd` (120 с).
+
+---
+
+## Validation
+
+Архитектурные инварианты и сценарии качества `QS-1`..`QS-6` проверяются автоматизированным набором тестов (`verification_surface` в `architecture-packet.json`):
+1. `pytest tests/test_detached_turn_execution.py -q` — проверка detached-выполнения, явной отмены `POST /v1/turns/<id>/cancel` с освобождением слота, точного `turn_key` при перегенерации, `410 GAP_DETECTED`, валидации `turn_id` (`^[a-zA-Z0-9_-]{1,64}$`), Bearer-авторизации, прав `0600`/`0700`, `schema_version: "1.0"` и passthrough неизвестных `kind` (`REQ-001`, `AD-001`, `RW-001`..`RW-003`, `RW-006`, `RW-010`, `FU-002`).
+2. `pytest tests/test_adaptive_idle_watchdog.py -q` — проверка сброса `idle_timeout` только при приросте `cputime` или событиях протокола, срабатывания `idle_timeout` на спящем дочернем процессе без прироста CPU, fail-closed режима при сбое `ps`, потолка `absolute_cap` (3600 с) и маркировки логов `rid`/`turn_id` (`REQ-002`, `AD-002`, `RW-005`, `FU-004`).
+3. `pytest tests/test_graceful_shutdown_drain.py -q` — проверка неблокирующего обработчика `SIGTERM`/`SIGINT` через `threading.Event`, фонового потока drain, зачистки сирот по `children.json` на старте (`orphan reaper`), ответа `503 Retry-After: 5`, фичефлагов `DSH_BRIDGE_*_ENABLED` и SSE keepalive `<= 10 с` (`REQ-004`, `AD-004`, `RW-004`, `RW-007`, `RW-009`).
+4. `pytest tests/test_backend_contract.py tests/test_hub_integration.py -q` — проверка единого контракта `core/` для `DroidAdapter` и `MuseAdapter`, отсутствия импорта `core.tool_emulation` в `core/turn_session_manager.py` и загрузки `core.*` в `bridges/muse-bridge/server.py` (`REQ-003`, `AD-003`, `RW-008`, `FU-003`).
+5. `pytest tests/test_dsh_profile_config.py -q` — проверка отсутствия `{{cwd}}` в `deployment:persona-suffix` профиля `~/.dsh/profiles/web/cordis.patch.yml` (`REQ-005`, `AD-005`).
diff --git a/receipts/arch-panel.json b/receipts/arch-panel.json
index 47831c3..506657d 100644
--- a/receipts/arch-panel.json
+++ b/receipts/arch-panel.json
@@ -1,7 +1,7 @@
 {
-  "artifact_sha256": "75eab5226b549adc06c133e6072c26054d825784ba7bf3c48db903ff61e0e172",
+  "artifact_sha256": "86de86783a9eaba1d866955443f59cc31da128d715585456898b9590100ed206",
   "expect_seats": 3,
-  "manifest_sha256": "bdea91f72a809a2be841795a34ef5cb13c82bd205816cc9f5dddef087f3b36fa",
+  "manifest_sha256": "d06a7635b625b133acac0129c48fb3afa4a389c751cbe74d33646edc181f7a8a",
   "min_seconds": 8.0,
   "min_verdict_chars": 200,
   "result": "PASS",
@@ -9,40 +9,40 @@
   "schema": "pol-receipt/1",
   "seats": [
     {
-      "duration_s": 119.410948,
-      "family": "Google",
+      "duration_s": 131.080734,
+      "family": "Meta",
       "k": 1,
-      "launch_sha256": "82645dded9e1aa091db06e64b85103b00e88c1dd425800883d812269a98c33ba",
-      "raw_out_sha256": "c1e591bf425d4f19cd7893ac2eee710c8600e16764e75d94b46991305e5ff1c9",
+      "launch_sha256": "dba58da844f26b72f6ddcfc730c2baa88894124cce379338b43603f2511226eb",
+      "raw_out_sha256": "cc435a8984e112eb260dfb5278cd44e749bd48ae38eb2da328419bc644831761",
+      "rc": 0,
+      "slot_id": "muse-wonder-full-1.0",
+      "transport": "muse",
+      "verdict": "ACCEPT",
+      "verdict_sha256": "72b1b1f393c3a7ff7d981757ea50b47dfb99f30e506be6c2f88f289cc4633a29"
+    },
+    {
+      "duration_s": 127.977531,
+      "family": "Google",
+      "k": 2,
+      "launch_sha256": "ae6dc0a8d31f0ea5a967d386dda69f6d99cd9a86e8b840083b081f4b7f5e48dd",
+      "raw_out_sha256": "a95261b29f939bd268d7c71ca7abceb86a099581244290427d49854c68d92141",
       "rc": 0,
       "slot_id": "gemini-4-argon-high",
       "transport": "agy",
       "verdict": "ACCEPT",
-      "verdict_sha256": "9549bede489868e302641d8486b2e3b55acb97fb2510e3541e5c3dfd8857cf53"
+      "verdict_sha256": "338b58841b601225b6f87c94d21c153d2c296b78daeb230109ff9e4b554aa646"
     },
     {
-      "duration_s": 77.746952,
+      "duration_s": 76.357816,
       "family": "Anthropic",
-      "k": 2,
-      "launch_sha256": "bfe6ac86922b9ea2cf58b6005030035108fa7f75bb68da6f526a7d56d4f8ee5f",
-      "raw_out_sha256": "fc9398bf151eab020e1659f09e882d61f5640f77aa90ab2e5b2081d30e976cdd",
+      "k": 3,
+      "launch_sha256": "49affe1275b8bb527c2aa7cd75273a92a08ca2b226566b5aa0a0c7db4df4bbfe",
+      "raw_out_sha256": "b315a7371239c78f13ef27de7e28d5c861cb429fd128414970d1f30811adae66",
       "rc": 0,
       "slot_id": "claude-sonnet-5-5-high",
       "transport": "claude-p",
       "verdict": "NEEDS_WORK",
-      "verdict_sha256": "e83ae2b7fabb717c6a638b77de4c4c5bdcd9c1d60f067e09b3acd23945e51c9e"
-    },
-    {
-      "duration_s": 77.4156,
-      "family": "Meta",
-      "k": 3,
-      "launch_sha256": "919b9749011cc5e88c5a48aeb1172704795198a25e08272f0f33d935c928e4b7",
-      "raw_out_sha256": "ecbad8b697ed75047984a576bc7210fc52df3419aa9a8071723926209017bc88",
-      "rc": 0,
-      "slot_id": "muse-wonder-full-1.0",
-      "transport": "muse",
-      "verdict": "ACCEPT",
-      "verdict_sha256": "f092d641137eacf77a57382677244d94fb98e530cb40b30a125feb675597ab5e"
+      "verdict_sha256": "346c181d9e2ad73e0cd52db86cfc748ec783414e22a0b7351aeca006a0bbc115"
     }
   ],
   "stage": "arch",
@@ -50,6 +50,6 @@
     "ACCEPT": 2,
     "NEEDS_WORK": 1
   },
-  "verified_at": "2026-10-17T12:41:23.924364+00:00",
+  "verified_at": "2026-10-17T17:46:44.826408+00:00",
   "verifier_sha256": "8138eae56e674689aecd15c5eacc7ebfdda952ce806231ca2f8c4c3f17bae996"
 }
diff --git a/server.py b/server.py
index 46471c4..b048822 100644
--- a/server.py
+++ b/server.py
@@ -43,6 +43,7 @@ import collections
 import fcntl
 import functools
 import hashlib
+import hmac
 import itertools
 import json
 import os
@@ -89,6 +90,10 @@ from core.backend_adapter import (  # noqa: E402
     TurnContext,
     build_catalog,
 )
+from core.lifecycle import (  # noqa: E402
+    DEFAULT_DRAIN_SECONDS,
+    HubLifecycleManager,
+)
 from core.tool_emulation import (  # noqa: E402,F401  - общая эмуляция tools (MB-REQ-007), реэкспорт имён
     TOOL_CALL_CLOSE,
     TOOL_CALL_OPEN,
@@ -109,7 +114,24 @@ from core.tool_emulation import (  # noqa: E402,F401  - общая эмуляц
     _tools_section,
     finalize_turn,
 )
+from core.turn_session_manager import (  # noqa: E402
+    GapDetectedError,
+    ManagedTurn,
+    TurnSessionManager,
+    _is_detached_enabled,
+    _is_drain_enabled,
+    _is_watchdog_enabled,
+    hash_token,
+    validate_turn_id,
+)
 from core.usage_wire import normalize_prompt_cache_details  # noqa: E402
+from core.watchdog import (  # noqa: E402,F401
+    DEFAULT_IDLE_TIMEOUT_S,
+    DEFAULT_SAFETY_CAP_S,
+    AdaptiveTimeoutController,
+    ProcessWatchdog,
+)
+
 
 HOME = Path.home()
 HOST = os.environ.get("DROID_DSH_BRIDGE_HOST", "127.0.0.1")
@@ -127,7 +149,13 @@ WORKSPACE = ROOT / "workspace"
 MAX_CONCURRENT = int(os.environ.get("DROID_DSH_BRIDGE_MAX_CONCURRENT", "4"))
 QUEUE_TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_QUEUE_TIMEOUT", "900"))
 TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_TIMEOUT", "1800"))
-KEEPALIVE_S = float(os.environ.get("DROID_DSH_BRIDGE_KEEPALIVE", "15"))
+KEEPALIVE_S = min(10.0, float(os.environ.get("DROID_DSH_BRIDGE_KEEPALIVE", "10")))
+IDLE_TIMEOUT_S = float(
+    os.environ.get("DROID_DSH_BRIDGE_IDLE_TIMEOUT_S", str(int(DEFAULT_IDLE_TIMEOUT_S)))
+)
+SAFETY_CAP_S = float(
+    os.environ.get("DROID_DSH_BRIDGE_SAFETY_CAP_S", str(int(DEFAULT_SAFETY_CAP_S)))
+)
 # RW-009 в живом ходе: запись живого куска клиенту ограничена этим таймаутом (а не 300с
 # socket-таймаута соединения) — зависший/нечитающий клиент не держит T/L (см. sse_writer в
 # _serve_sse и add_content/add_reasoning в Handler._execute).
@@ -550,11 +578,30 @@ def _image_proof_reason(model: dict, effort: str = "") -> str:
     return ""
 
 
+def _extract_auth_token(handler: BaseHTTPRequestHandler) -> str:
+    hdr = handler.headers.get("Authorization", "")
+    if hdr.startswith("Bearer "):
+        return hdr[7:].strip()
+    return handler.headers.get("x-api-key", "") or hdr.strip()
+
+
 def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
     hdr = handler.headers.get("Authorization", "")
     if hdr.startswith("Bearer "):
-        return hdr[7:].strip() == AUTH_KEY
-    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY
+        return hmac.compare_digest(
+            hdr[7:].strip().encode("utf-8"), AUTH_KEY.encode("utf-8")
+        )
+    return hmac.compare_digest(
+        handler.headers.get("x-api-key", "").encode("utf-8"),
+        AUTH_KEY.encode("utf-8"),
+    ) or hmac.compare_digest(
+        hdr.strip().encode("utf-8"),
+        AUTH_KEY.encode("utf-8"),
+    )
+
+
+def _owner_token_hash(handler: BaseHTTPRequestHandler) -> str:
+    return hash_token(_extract_auth_token(handler) or AUTH_KEY)
 
 
 class ImageReject(Exception):
@@ -2103,6 +2150,38 @@ REGISTRY = ChatRegistry()
 POOL = ProcPool()
 
 
+def _active_turn_count() -> int:
+    return max(BACKENDS.active_total(), TURN_MANAGER.active_count())
+
+
+def _force_kill_all_on_drain() -> None:
+    TURN_MANAGER.kill_all_active()
+    shutdown_all(grace=2.0)
+    BACKENDS.shutdown(exclude=("droid",))
+    try:
+        _sweep_workspace(cutoff_s=0.0)
+    except Exception:  # noqa: BLE001
+        pass
+
+
+TURN_MANAGER = TurnSessionManager(
+    _state_dir,
+    max_concurrent=max(MAX_CONCURRENT * 8, 32),
+    finalize_fn=finalize_turn,
+    log_fn=_log,
+    persist_children_file=False,
+)
+LIFECYCLE = HubLifecycleManager(
+    state_dir=_state_dir,
+    turn_manager=TURN_MANAGER,
+    active_turns_fn=_active_turn_count,
+    force_kill_fn=_force_kill_all_on_drain,
+    drain_timeout_s=DEFAULT_DRAIN_SECONDS,
+    log_fn=_log,
+)
+
+
+
 def _reset_rpc_state() -> None:
     """Закрыть всех детей и сбросить реестр/пул (тесты; старт моста)."""
     global REGISTRY, POOL, _shutting_down
@@ -2112,6 +2191,8 @@ def _reset_rpc_state() -> None:
         proc.close(mode="term", term_wait=1.0, kill_wait=1.0)
     REGISTRY = ChatRegistry()  # pyright: ignore[reportConstantRedefinition]
     POOL = ProcPool()  # pyright: ignore[reportConstantRedefinition]
+    TURN_MANAGER.reset_state()
+    LIFECYCLE.reset_state()
     _shutting_down = False
 
 
@@ -3595,6 +3676,9 @@ def _client_gone(sock: socket.socket) -> bool:
         return True
 
 
+_DEFAULT_CLIENT_GONE = _client_gone
+
+
 class _ByteBudget:
     """Резерв байт admission по заявленному Content-Length (C-11)."""
 
@@ -3627,6 +3711,8 @@ class Handler(BaseHTTPRequestHandler):
     timeout = 300
     _delivery_reserved = 0  # байты, взятые в _DELIVERY_BUDGET текущим запросом (RW-011)
     _client_write_dead = False  # RW-203: живая запись отвергнута — терминал не шлём
+    _active_managed_turn: ManagedTurn | None = None
+    _detach_on_disconnect = False
 
     def log_message(self, fmt: str, *args: Any) -> None:
         _log("http " + (fmt % args))
@@ -3637,13 +3723,24 @@ class Handler(BaseHTTPRequestHandler):
     def _client_tag(self) -> str:
         return f"{self.client_address[0]}:{self.client_address[1]}"
 
-    def _send(self, code: int, payload: dict) -> None:
+    def _send(
+        self,
+        code: int,
+        payload: dict,
+        extra_headers: dict[str, str] | None = None,
+    ) -> None:
         body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
-        self.send_response(int(code))
-        self.send_header("Content-Type", "application/json; charset=utf-8")
-        self.send_header("Content-Length", str(len(body)))
-        self.end_headers()
-        self.wfile.write(body)
+        try:
+            self.send_response(int(code))
+            self.send_header("Content-Type", "application/json; charset=utf-8")
+            self.send_header("Content-Length", str(len(body)))
+            for hdr_k, hdr_v in (extra_headers or {}).items():
+                self.send_header(str(hdr_k), str(hdr_v))
+            self.end_headers()
+            self.wfile.write(body)
+        except (BrokenPipeError, ConnectionResetError, OSError):
+            if not getattr(self, "_detach_on_disconnect", False):
+                raise
 
     def _emit(self, data: str) -> bool:
         try:
@@ -3669,12 +3766,15 @@ class Handler(BaseHTTPRequestHandler):
         message: str,
         model: str = "unknown",
         model_len: int = 0,
+        extra_headers: dict[str, str] | None = None,
     ) -> None:
         """Отказ (до SSE): строка `reject …` в журнал и общий формат ошибки."""
         self._log_reject(reason, model, model_len)
         self.close_connection = True
         self._send(
-            code, {"error": {"message": message, "type": reason, "code": int(code)}}
+            code,
+            {"error": {"message": message, "type": reason, "code": int(code)}},
+            extra_headers=extra_headers,
         )
 
     def _acquire_slot(self, keepalive):
@@ -3726,6 +3826,13 @@ class Handler(BaseHTTPRequestHandler):
             None
         ]  # mid последнего content-куска в pieces (разделитель "\n\n" между сообщениями)
         pushback = None  # элемент очереди, подсмотренный при коалесации, но не обработанный сейчас
+        managed_turn = getattr(self, "_active_managed_turn", None)
+        detach_on_disconnect = bool(getattr(self, "_detach_on_disconnect", False))
+        watchdog_enabled = os.environ.get(
+            "BRIDGE_ADAPTIVE_WATCHDOG_ENABLED", "true"
+        ).strip().lower() in ("1", "true", "yes", "on")
+        proc_watchdog = ProcessWatchdog(log_fn=_log) if watchdog_enabled else None
+        watchdog_seeded_pid = [0]
 
         def state(name: str, rc: int, err: str = "") -> dict:
             return {
@@ -3757,8 +3864,12 @@ class Handler(BaseHTTPRequestHandler):
                 return
             pieces.append(text)
             events.append(("content", text))
-            if sse_writer is not None and not self._client_write_dead:
+            if sse_writer is not None:
                 for piece in _text_slices(text):
+                    if managed_turn is not None and not managed_turn.buffer.sealed:
+                        managed_turn.buffer.append("content", piece)
+                    if self._client_write_dead:
+                        continue
                     # RW-011 в живом ходе: бюджет резервируется ДО фактической отдачи
                     # куска — ничего незарезервированного клиенту не покажется. Бюджет
                     # считается в байтах UTF-8 (RW-206): piece может содержать кириллицу/
@@ -3769,21 +3880,37 @@ class Handler(BaseHTTPRequestHandler):
                     self._delivery_reserved += piece_bytes
                     if not sse_writer("content", piece):
                         self._client_write_dead = True
-                        break
+                        if managed_turn is not None and detach_on_disconnect:
+                            TURN_MANAGER.mark_detached(managed_turn.turn_id)
+                        else:
+                            break
+            elif managed_turn is not None and not managed_turn.buffer.sealed:
+                for piece in _text_slices(text):
+                    managed_turn.buffer.append("content", piece)
 
         def add_reasoning(text: str) -> None:
             if not text:
                 return
             events.append(("reasoning", text))
-            if sse_writer is not None and not self._client_write_dead:
+            if sse_writer is not None:
                 for piece in _text_slices(text):
+                    if managed_turn is not None and not managed_turn.buffer.sealed:
+                        managed_turn.buffer.append("reasoning", piece)
+                    if self._client_write_dead:
+                        continue
                     piece_bytes = len(piece.encode("utf-8"))
                     if not _DELIVERY_BUDGET.reserve(piece_bytes):
                         raise _LiveBudgetExceeded()
                     self._delivery_reserved += piece_bytes
                     if not sse_writer("reasoning", piece):
                         self._client_write_dead = True
-                        break
+                        if managed_turn is not None and detach_on_disconnect:
+                            TURN_MANAGER.mark_detached(managed_turn.turn_id)
+                        else:
+                            break
+            elif managed_turn is not None and not managed_turn.buffer.sealed:
+                for piece in _text_slices(text):
+                    managed_turn.buffer.append("reasoning", piece)
 
         def add_call(call: dict) -> None:
             entry = {
@@ -3797,6 +3924,8 @@ class Handler(BaseHTTPRequestHandler):
             }
             tool_calls.append(entry)
             events.append(("tool_call", entry))
+            if managed_turn is not None:
+                managed_turn.buffer.append("tool_call", entry)
 
         parser = (
             ToolCallParser(add_content, add_call, strict_live=sse_writer is not None)
@@ -3812,6 +3941,22 @@ class Handler(BaseHTTPRequestHandler):
             return run.q.get(timeout=1.0)
 
         while True:
+            rproc = getattr(run, "proc", None)
+            if (
+                rproc is not None
+                and getattr(rproc, "pid", 0)
+                and watchdog_seeded_pid[0] != rproc.pid
+            ):
+                watchdog_seeded_pid[0] = rproc.pid
+                if proc_watchdog is not None:
+                    proc_watchdog.seed(rproc.pid)
+                if managed_turn is not None:
+                    managed_turn.bind_process(
+                        pgid=rproc.pid, terminate_fn=run.close
+                    )
+            if managed_turn is not None and managed_turn.cancel_event.is_set():
+                run.cancel.set()
+                return state("client_gone", 1, "turn cancelled")
             if time.monotonic() > deadline:
                 return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
             if (
@@ -3828,12 +3973,28 @@ class Handler(BaseHTTPRequestHandler):
                 and run.last_progress
                 and time.monotonic() - run.last_progress > SILENCE_WATCHDOG_S
             ):
-                # Тишина: сбрасывают только события ТЕКУЩЕГО хода (не keepalive/чужие).
-                return state(
-                    "timeout", 124, f"no droid progress within {SILENCE_WATCHDOG_S:g}s"
-                )
-            if _client_gone(self.connection):
-                return state("client_gone", 1)
+                if (
+                    SILENCE_WATCHDOG_S >= 10.0
+                    and proc_watchdog is not None
+                    and rproc is not None
+                    and getattr(rproc, "pid", 0)
+                    and proc_watchdog.sample(rproc.pid).has_progress
+                ):
+                    run.last_progress = time.monotonic()
+                else:
+                    # Тишина: сбрасывают только события ТЕКУЩЕГО хода (не keepalive/чужие).
+                    return state(
+                        "timeout",
+                        124,
+                        f"no droid progress within {SILENCE_WATCHDOG_S:g}s",
+                    )
+            if not self._client_write_dead and _client_gone(self.connection):
+                if detach_on_disconnect:
+                    self._client_write_dead = True
+                    if managed_turn is not None:
+                        TURN_MANAGER.mark_detached(managed_turn.turn_id)
+                else:
+                    return state("client_gone", 1)
             try:
                 kind, payload = take()
             except queue.Empty:
@@ -3865,7 +4026,12 @@ class Handler(BaseHTTPRequestHandler):
                 ):
                     last_ka = time.monotonic()
                     if not keepalive():
-                        return state("client_gone", 1)
+                        if detach_on_disconnect:
+                            self._client_write_dead = True
+                            if managed_turn is not None:
+                                TURN_MANAGER.mark_detached(managed_turn.turn_id)
+                        else:
+                            return state("client_gone", 1)
                 continue
             if kind in ("text_delta", "reasoning_delta"):
                 group_mid, buf0 = payload
@@ -4136,6 +4302,17 @@ class Handler(BaseHTTPRequestHandler):
                     old.close(mode="term", keep_slot=True)
                     holds_slot = True
                 t_held = False
+                t_released = [False]
+
+                def _release_turn_slot() -> None:
+                    if t_held and not t_released[0]:
+                        t_released[0] = True
+                        _slots.release()
+
+                managed_turn = getattr(self, "_active_managed_turn", None)
+                if managed_turn is not None:
+                    managed_turn._slot_release_fn = _release_turn_slot
+                    managed_turn._slot_released = False
                 new_run = None
                 try:
                     # Любая ошибка между взятием слотов P/T и созданием Run возвращает их (RW-012):
@@ -4193,7 +4370,7 @@ class Handler(BaseHTTPRequestHandler):
                             stale, chat.proc = chat.proc, None
                             if stale is not None:
                                 _close_async(stale, "term")
-                            _slots.release()
+                            _release_turn_slot()
                             t_held = False
                             if holds_slot:
                                 POOL.release()
@@ -4222,11 +4399,19 @@ class Handler(BaseHTTPRequestHandler):
                         holds_slot,
                         sse_writer,
                     )
+                    if managed_turn is not None:
+                        managed_turn.bind_process(
+                            pgid=getattr(new_run, "pgid", None)
+                            or getattr(getattr(new_run, "proc", None), "pid", None),
+                            terminate_fn=lambda p=getattr(new_run, "proc", None): (
+                                _close_async(p, "kill") if p is not None else None
+                            ),
+                        )
                     holds_slot = False
                 except Exception as exc:  # noqa: BLE001 - любая ошибка подготовки хода: ресурсы назад, штатный 502
                     if new_run is None:
                         if t_held:
-                            _slots.release()
+                            _release_turn_slot()
                         if holds_slot:
                             POOL.release()
                     _log(
@@ -4247,7 +4432,7 @@ class Handler(BaseHTTPRequestHandler):
                 except BaseException:
                     if new_run is None:
                         if t_held:
-                            _slots.release()
+                            _release_turn_slot()
                         if holds_slot:
                             POOL.release()
                     raise
@@ -4261,7 +4446,9 @@ class Handler(BaseHTTPRequestHandler):
                     try:
                         run.close()
                     finally:
-                        _slots.release()
+                        if managed_turn is not None:
+                            managed_turn.release_slot_once()
+                        _release_turn_slot()
                 ok = bool(run.ok and out.get("state") == "done" and out.get("rc") == 0)
                 try:
                     committed_turns = _finish_attempt(
@@ -4373,6 +4560,14 @@ class Handler(BaseHTTPRequestHandler):
                 "type": "timeout",
                 "code": 504,
             }
+        if st in ("idle_timeout", "safety_cap"):
+            return {
+                "message": str(
+                    out.get("err") or f"{label} exec timed out after {TIMEOUT_S}s"
+                )[:500],
+                "type": "timeout",
+                "code": 504,
+            }
         if st == "first_token_timeout":
             return {
                 "message": f"first_token_timeout: droid exec gave no event within "
@@ -4475,6 +4670,107 @@ class Handler(BaseHTTPRequestHandler):
         self._delivery_reserved += size
         return None
 
+    def _parse_from_seq(self) -> int | None:
+        raw_seq = None
+        if "?" in self.path:
+            qs = self.path.split("?", 1)[1]
+            for part in qs.split("&"):
+                if part.startswith("from_seq="):
+                    raw_seq = part.split("=", 1)[1]
+                    break
+        if raw_seq is None:
+            hdr_seq = self.headers.get("Last-Event-ID")
+            if hdr_seq is not None and hdr_seq.strip():
+                raw_seq = hdr_seq.strip()
+        if raw_seq is None or raw_seq == "":
+            return 0
+        if not re.fullmatch(r"[0-9]+", str(raw_seq).strip()):
+            return None
+        return int(str(raw_seq).strip())
+
+    def _serve_turn_stream(self, turn_id: str) -> None:
+        if not validate_turn_id(turn_id):
+            self._send(
+                400,
+                {
+                    "error": {
+                        "message": "invalid turn_id",
+                        "type": "invalid_request",
+                        "code": 400,
+                    }
+                },
+            )
+            return
+        from_seq = self._parse_from_seq()
+        if from_seq is None:
+            self._send(
+                400,
+                {
+                    "error": {
+                        "message": "invalid from_seq",
+                        "type": "invalid_request",
+                        "code": 400,
+                    }
+                },
+            )
+            return
+        try:
+            turn = TURN_MANAGER.get_turn(
+                turn_id, owner_token_hash=_owner_token_hash(self)
+            )
+        except KeyError:
+            self._send(
+                404,
+                {
+                    "error": {
+                        "message": f"turn not found: {turn_id}",
+                        "type": "not_found",
+                        "code": 404,
+                    }
+                },
+            )
+            return
+        except PermissionError:
+            self._send(
+                403,
+                {
+                    "error": {
+                        "message": "turn belongs to another token",
+                        "type": "forbidden",
+                        "code": 403,
+                    }
+                },
+            )
+            return
+        try:
+            turn.buffer.get_since(
+                from_seq,
+                turn_id=turn.turn_id,
+                state_dump_path=turn.state_dump_path,
+            )
+        except GapDetectedError as exc:
+            self._send(410, exc.to_http_payload())
+            return
+        try:
+            self.send_response(200)
+            self.send_header("Content-Type", "text/event-stream")
+            self.send_header("Cache-Control", "no-cache")
+            self.send_header("X-Accel-Buffering", "no")
+            self.send_header("X-Turn-Id", turn.turn_id)
+            self.end_headers()
+            self.close_connection = True
+        except (BrokenPipeError, ConnectionResetError, OSError):
+            return
+        for frame in TURN_MANAGER.iter_sse_stream(
+            turn,
+            from_seq=from_seq,
+            keepalive_interval_s=min(10.0, KEEPALIVE_S),
+            client_gone_fn=lambda: _client_gone(self.connection),
+        ):
+            if not self._emit(frame):
+                TURN_MANAGER.mark_detached(turn.turn_id)
+                return
+
     # ---- HTTP --------------------------------------------------------------------
     def do_GET(self) -> None:  # noqa: N802
         path = self.path.split("?", 1)[0]
@@ -4483,6 +4779,7 @@ class Handler(BaseHTTPRequestHandler):
             # бэкендам (droid: невалидный receipt = spawn невозможен -> ok=false, RW-015),
             # active и max_concurrent суммируются по включённым бэкендам.
             required = [a for a in BACKENDS.adapters() if a.required]
+            draining = _shutting_down or (_is_drain_enabled() and LIFECYCLE.is_draining())
             self._send(
                 200,
                 {
@@ -4494,6 +4791,7 @@ class Handler(BaseHTTPRequestHandler):
                     "tool_emulation": True,
                     "uptime_s": int(time.time() - _started),
                 },
+                extra_headers={"X-Bridge-Draining": "1"} if draining else None,
             )
             return
         if not _auth_ok(self):
@@ -4528,6 +4826,56 @@ class Handler(BaseHTTPRequestHandler):
                 )
             self._send(200, {"object": "list", "data": data})
             return
+        if _is_detached_enabled() and path.startswith("/v1/turns/"):
+            m_stream = re.fullmatch(r"/v1/turns/([^/]+)/stream", path)
+            if m_stream:
+                self._serve_turn_stream(m_stream.group(1))
+                return
+            m_turn = re.fullmatch(r"/v1/turns/([^/]+)", path)
+            if m_turn:
+                turn_id = m_turn.group(1)
+                if not validate_turn_id(turn_id):
+                    self._send(
+                        400,
+                        {
+                            "error": {
+                                "message": "invalid turn_id",
+                                "type": "invalid_request",
+                                "code": 400,
+                            }
+                        },
+                    )
+                    return
+                try:
+                    snap = TURN_MANAGER.get_turn_snapshot(
+                        turn_id, owner_token_hash=_owner_token_hash(self)
+                    )
+                except KeyError:
+                    self._send(
+                        404,
+                        {
+                            "error": {
+                                "message": f"turn not found: {turn_id}",
+                                "type": "not_found",
+                                "code": 404,
+                            }
+                        },
+                    )
+                    return
+                except PermissionError:
+                    self._send(
+                        403,
+                        {
+                            "error": {
+                                "message": "turn belongs to another token",
+                                "type": "forbidden",
+                                "code": 403,
+                            }
+                        },
+                    )
+                    return
+                self._send(200, snap)
+                return
         self._send(
             404,
             {
@@ -4539,9 +4887,96 @@ class Handler(BaseHTTPRequestHandler):
             },
         )
 
+    def do_DELETE(self) -> None:  # noqa: N802
+        if not _auth_ok(self):
+            self.close_connection = True
+            self._send(
+                401,
+                {
+                    "error": {
+                        "message": "unauthorized",
+                        "type": "auth_error",
+                        "code": 401,
+                    }
+                },
+            )
+            return
+        path = self.path.split("?", 1)[0]
+        m_turn = re.fullmatch(r"/v1/turns/([^/]+)", path) if _is_detached_enabled() else None
+        if not m_turn:
+            self._send(
+                404,
+                {
+                    "error": {
+                        "message": f"not found: {path}",
+                        "type": "not_found",
+                        "code": 404,
+                    }
+                },
+            )
+            return
+        turn_id = m_turn.group(1)
+        if not validate_turn_id(turn_id):
+            self._send(
+                400,
+                {
+                    "error": {
+                        "message": "invalid turn_id",
+                        "type": "invalid_request",
+                        "code": 400,
+                    }
+                },
+            )
+            return
+        owner_hash = _owner_token_hash(self)
+        try:
+            TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
+            snap = TURN_MANAGER.get_turn_snapshot(turn_id, owner_token_hash=owner_hash)
+        except KeyError:
+            self._send(
+                404,
+                {
+                    "error": {
+                        "message": f"turn not found: {turn_id}",
+                        "type": "not_found",
+                        "code": 404,
+                    }
+                },
+            )
+            return
+        except PermissionError:
+            self._send(
+                403,
+                {
+                    "error": {
+                        "message": "turn belongs to another token",
+                        "type": "forbidden",
+                        "code": 403,
+                    }
+                },
+            )
+            return
+        self._send(200, snap)
+
     def do_POST(self) -> None:  # noqa: N802
-        if _shutting_down:
-            self._reject(503, "overloaded", "bridge is shutting down")
+        self._active_managed_turn = None
+        managed_turn: ManagedTurn | None = None
+        attached_existing = False
+        path = self.path.split("?", 1)[0]
+        m_cancel = (
+            re.fullmatch(r"/v1/turns/([^/]+)/cancel", path)
+            if _is_detached_enabled()
+            else None
+        )
+        if not m_cancel and (
+            _shutting_down or (_is_drain_enabled() and LIFECYCLE.is_draining())
+        ):
+            self._reject(
+                503,
+                "overloaded",
+                "bridge is shutting down",
+                extra_headers={"Retry-After": "5", "X-Bridge-Draining": "1"},
+            )
             return
         if not _auth_ok(self):
             # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
@@ -4591,6 +5026,45 @@ class Handler(BaseHTTPRequestHandler):
             if len(raw) < length:
                 self._reject(400, "invalid_request", "request body truncated")
                 return
+            if m_cancel is not None:
+                turn_id = m_cancel.group(1)
+                if not validate_turn_id(turn_id):
+                    self._reject(400, "invalid_request", "invalid turn_id")
+                    return
+                owner_hash = _owner_token_hash(self)
+                try:
+                    TURN_MANAGER.cancel_turn(turn_id, owner_token_hash=owner_hash)
+                    snap = TURN_MANAGER.get_turn_snapshot(
+                        turn_id, owner_token_hash=owner_hash
+                    )
+                except KeyError:
+                    self.close_connection = True
+                    self._send(
+                        404,
+                        {
+                            "error": {
+                                "message": f"turn not found: {turn_id}",
+                                "type": "not_found",
+                                "code": 404,
+                            }
+                        },
+                    )
+                    return
+                except PermissionError:
+                    self.close_connection = True
+                    self._send(
+                        403,
+                        {
+                            "error": {
+                                "message": "turn belongs to another token",
+                                "type": "forbidden",
+                                "code": 403,
+                            }
+                        },
+                    )
+                    return
+                self._send(200, snap)
+                return
             # (5) JSON и (6) JSON-объект.
             try:
                 req = json.loads(raw.decode("utf-8"))
@@ -4601,7 +5075,6 @@ class Handler(BaseHTTPRequestHandler):
                 self._reject(400, "invalid_request", "request must be a JSON object")
                 return
             # (7) путь.
-            path = self.path.split("?", 1)[0]
             if path not in ("/v1/chat/completions", "/chat/completions"):
                 self.close_connection = True
                 self._send(
@@ -4758,6 +5231,23 @@ class Handler(BaseHTTPRequestHandler):
                 req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
             )
             cwd = str(extra.get("cwd") or "")
+            req_turn_id = (
+                self.headers.get("X-Turn-Id") or str(extra.get("turn_id") or "")
+            ).strip()
+            resume_turn_id = (
+                self.headers.get("X-Resume-Turn-Id")
+                or str(extra.get("resume_turn_id") or "")
+            ).strip()
+            for candidate_tid in (req_turn_id, resume_turn_id):
+                if candidate_tid and not validate_turn_id(candidate_tid):
+                    self._reject(
+                        400,
+                        "invalid_request",
+                        "invalid turn_id",
+                        model_id,
+                        model_len,
+                    )
+                    return
             # Маршрут хода: нового 400 на ключ нет — плохой/отсутствующий ключ = холодная
             # изолированная сессия с replay истории запроса.
             transcript = _transcribe(messages, tools, tool_choice, images)
@@ -4785,6 +5275,64 @@ class Handler(BaseHTTPRequestHandler):
             )
             if instr is None:
                 return
+            is_legacy_muse_sleep = (
+                model["backend"] == "muse"
+                and not req_turn_id
+                and not resume_turn_id
+                and not keyed
+                and (Path(getattr(adapter, "wrapper", "")).parent / "mode").is_file()
+                and (Path(getattr(adapter, "wrapper", "")).parent / "mode")
+                .read_text(encoding="utf-8", errors="ignore")
+                .strip()
+                == "sleep"
+            )
+            detach_on_disconnect = (
+                _is_detached_enabled()
+                and (
+                    _client_gone is _DEFAULT_CLIENT_GONE
+                    or bool(req_turn_id or resume_turn_id)
+                )
+                and not is_legacy_muse_sleep
+            )
+            managed_turn: ManagedTurn | None = None
+            attached_existing = False
+            if _is_detached_enabled():
+                try:
+                    managed_turn, attached_existing = (
+                        TURN_MANAGER.create_or_attach_turn(
+                            model=model_id,
+                            backend=model["backend"],
+                            cwd=cwd,
+                            messages=messages,
+                            session_id=raw_key if keyed else "",
+                            owner_token_hash=_owner_token_hash(self),
+                            requested_turn_id=req_turn_id or None,
+                            resume_turn_id=resume_turn_id or None,
+                            stream=bool(req.get("stream")),
+                            emulate_tools=emulate_tools,
+                            idle_timeout_s=(
+                                SILENCE_WATCHDOG_S
+                                if _is_watchdog_enabled()
+                                else TIMEOUT_S
+                            ),
+                            safety_cap_s=TIMEOUT_S,
+                        )
+                    )
+                except PermissionError:
+                    self._reject(
+                        403,
+                        "forbidden",
+                        "turn belongs to another token",
+                        model_id,
+                        model_len,
+                    )
+                    return
+                except ValueError as exc:
+                    self._reject(
+                        400, "invalid_request", str(exc), model_id, model_len
+                    )
+                    return
+            self._active_managed_turn = managed_turn
             ctx = {
                 "route": route,
                 "key_hash": _key_hash(raw_key)
@@ -4808,12 +5356,23 @@ class Handler(BaseHTTPRequestHandler):
                     f"ua={(self.headers.get('User-Agent') or '-')[:60]}"
                 ),
                 "stream": bool(req.get("stream")),
+                "turn_id": managed_turn.turn_id if managed_turn is not None else "",
+                "managed_turn": managed_turn,
+                "detach_on_disconnect": detach_on_disconnect,
+                "attached_existing": attached_existing,
             }
             if ctx["stream"]:
                 self._serve_sse(ctx)
             else:
                 self._serve_json(ctx)
         finally:
+            if (
+                managed_turn is not None
+                and not attached_existing
+                and managed_turn.is_active
+            ):
+                TURN_MANAGER.finalize_abandoned_turn(managed_turn)
+            self._active_managed_turn = None
             if reserved and budget is not None:
                 budget.release(reserved)
             _DELIVERY_BUDGET.release(self._delivery_reserved)
@@ -4899,6 +5458,13 @@ class Handler(BaseHTTPRequestHandler):
         отдавать content/reasoning по мере готовности (сейчас — droid), сами вызывают его из
         своего пути выполнения. Остальные (muse) его просто игнорируют — поведение не меняется.
         """
+        managed_turn: ManagedTurn | None = ctx.get("managed_turn") or getattr(
+            self, "_active_managed_turn", None
+        )
+        if ctx.get("attached_existing") and managed_turn is not None:
+            managed_turn.done_event.wait(timeout=TIMEOUT_S)
+            if managed_turn.final_dict is not None:
+                return dict(managed_turn.final_dict)
         adapter = BACKENDS.get(ctx["backend"])
         if adapter is None:
             return {
@@ -4914,7 +5480,9 @@ class Handler(BaseHTTPRequestHandler):
         transcript = ctx["rpc"]
         turn = TurnContext(
             **{
-                key: value for key, value in ctx.items() if key not in ("rpc", "images")
+                key: value
+                for key, value in ctx.items()
+                if key not in ("rpc", "images", "attached_existing")
             },
             rpc=Transcript(
                 system=transcript["system"],
@@ -4927,9 +5495,12 @@ class Handler(BaseHTTPRequestHandler):
             client_gone=lambda: _client_gone(self.connection),
         )
         t0 = time.monotonic()
-        result = finalize_turn(
-            adapter.execute_turn(turn, sse_writer), turn.emulate_tools
-        )
+        raw_turn_result = adapter.execute_turn(turn, sse_writer)
+        result = finalize_turn(raw_turn_result, turn.emulate_tools)
+        if managed_turn is not None:
+            TURN_MANAGER.complete_turn_from_result(
+                managed_turn, result, backend_kind=adapter.kind
+            )
         # Только локальный HTTP-буфер: межмодульный seam уже вернул DTO.
         out = {
             "state": result.state,
@@ -5022,6 +5593,9 @@ class Handler(BaseHTTPRequestHandler):
         self.send_response(200)
         self.send_header("Content-Type", "application/json; charset=utf-8")
         self.send_header("Content-Length", str(total))
+        active_turn = getattr(self, "_active_managed_turn", None)
+        if active_turn is not None:
+            self.send_header("X-Turn-Id", active_turn.turn_id)
         self.end_headers()
         for index, value in enumerate(values):
             self.wfile.write(segments[index] + b'"')
@@ -5059,15 +5633,35 @@ class Handler(BaseHTTPRequestHandler):
         completion_id = f"chatcmpl-droid-{uuid.uuid4().hex[:12]}"
         created = int(time.time())
         shown_model = ctx["model"]
+        managed_turn: ManagedTurn | None = ctx.get("managed_turn") or getattr(
+            self, "_active_managed_turn", None
+        )
         try:
             self.send_response(200)
             self.send_header("Content-Type", "text/event-stream")
             self.send_header("Cache-Control", "no-cache")
             self.send_header("X-Accel-Buffering", "no")
+            if managed_turn is not None:
+                self.send_header("X-Turn-Id", managed_turn.turn_id)
             self.end_headers()
             self.close_connection = True
         except (BrokenPipeError, ConnectionResetError, OSError):
             _log("client gone before headers")
+            if managed_turn is not None and ctx.get("detach_on_disconnect"):
+                TURN_MANAGER.mark_detached(managed_turn.turn_id)
+            return
+
+        if ctx.get("attached_existing") and managed_turn is not None:
+            from_seq = self._parse_from_seq() or 0
+            for frame in TURN_MANAGER.iter_sse_stream(
+                managed_turn,
+                from_seq=from_seq,
+                keepalive_interval_s=min(10.0, KEEPALIVE_S),
+                client_gone_fn=lambda: _client_gone(self.connection),
+            ):
+                if not self._emit(frame):
+                    TURN_MANAGER.mark_detached(managed_turn.turn_id)
+                    return
             return
 
         def chunk(delta: dict, finish=None) -> str:
@@ -5152,7 +5746,11 @@ class Handler(BaseHTTPRequestHandler):
             return ok
 
         if not self._emit(chunk({"role": "assistant", "content": ""})):
-            return
+            if managed_turn is not None and ctx.get("detach_on_disconnect"):
+                self._client_write_dead = True
+                TURN_MANAGER.mark_detached(managed_turn.turn_id)
+            else:
+                return
         try:
             out = self._dispatch(ctx, keepalive, sse_writer)
         except Exception as exc:  # noqa: BLE001 - RW-211: клиенту нужен конверт, а не сырой сбой
@@ -5357,6 +5955,7 @@ def main() -> None:
         raise SystemExit(1)
     _sweep_workspace()
     reconcile_children()
+    LIFECYCLE.reap_startup_orphans()
     if RECEIPT_REQUIRED:
         try:
             _droid_image()
@@ -5376,9 +5975,13 @@ def main() -> None:
             reason = _image_proof_reason(model)
             if reason:
                 _log(f"image_proof_invalid model={mid} reason={reason}")
-    signal.signal(signal.SIGTERM, _kill_all)
-    signal.signal(signal.SIGINT, _kill_all)
     server = Server((HOST, PORT), Handler)
+    if _is_drain_enabled():
+        LIFECYCLE.install_signal_handlers()
+        LIFECYCLE.start_signal_watcher(server)
+    else:
+        signal.signal(signal.SIGTERM, _kill_all)
+        signal.signal(signal.SIGINT, _kill_all)
     _log(
         f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
         f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s"
@@ -5389,3 +5992,4 @@ def main() -> None:
 
 if __name__ == "__main__":
     main()
+
diff --git a/tests/test_adaptive_idle_watchdog.py b/tests/test_adaptive_idle_watchdog.py
new file mode 100644
index 0000000..d08dc82
--- /dev/null
+++ b/tests/test_adaptive_idle_watchdog.py
@@ -0,0 +1,135 @@
+import os
+import subprocess
+import unittest
+from typing import Any
+from unittest.mock import patch
+
+from core.watchdog import AdaptiveTimeoutController, ProcessWatchdog, WatchdogMetrics, parse_cputime
+
+
+class _FakeClock:
+    def __init__(self, now: float = 1000.0) -> None:
+        self.now = now
+
+    def __call__(self) -> float:
+        return self.now
+
+    def advance(self, seconds: float) -> None:
+        self.now += seconds
+
+
+class _StubWatchdog(ProcessWatchdog):
+    def __init__(self, metrics: WatchdogMetrics) -> None:
+        super().__init__(ps_timeout_s=2.0)
+        self._metrics = metrics
+
+    def seed(self, pgid: int, **_kwargs: Any) -> None:
+        pass
+
+    def sample(self, pgid: int, **_kwargs: Any) -> WatchdogMetrics:
+        return self._metrics
+
+
+class AdaptiveIdleWatchdogTests(unittest.TestCase):
+    def test_parse_cputime_formats(self) -> None:
+        self.assertAlmostEqual(parse_cputime("0:00.50"), 0.5)
+        self.assertAlmostEqual(parse_cputime("01:30.25"), 90.25)
+        self.assertAlmostEqual(parse_cputime("02:01:00.00"), 7260.0)
+        self.assertAlmostEqual(parse_cputime("1-00:00:00"), 86400.0)
+
+    def test_idle_300s_extended_by_cpu_or_descendant_progress(self) -> None:
+        clock = _FakeClock(1000.0)
+        active_metrics = WatchdogMetrics(
+            pgid=4321,
+            alive=True,
+            descendant_pids=(4321, 4322),
+            new_descendants=(4322,),
+            cpu_time_s=2.5,
+            cpu_delta_s=1.2,
+            ps_degraded=False,
+            sample_ts=1350.0,
+        )
+        wd = _StubWatchdog(active_metrics)
+        ctrl = AdaptiveTimeoutController(
+            idle_timeout_s=300.0,
+            safety_cap_s=3600.0,
+            watchdog=wd,
+            watchdog_enabled=True,
+            clock=clock,
+        )
+        ctrl.register_pgid(4321)
+
+        # Advance 350s without stdout/protocol output, but child has CPU & descendant progress
+        clock.advance(350.0)
+        should_stop, reason, metrics = ctrl.check(4321)
+        self.assertFalse(should_stop)
+        self.assertEqual(reason, "")
+        self.assertIsNotNone(metrics)
+        self.assertTrue(metrics.has_progress)
+
+        # Now child goes completely idle (no CPU delta, no new descendants) for another 305s
+        wd._metrics = WatchdogMetrics(
+            pgid=4321,
+            alive=True,
+            descendant_pids=(4321, 4322),
+            new_descendants=(),
+            cpu_time_s=2.5,
+            cpu_delta_s=0.0,
+            ps_degraded=False,
+            sample_ts=1655.0,
+        )
+        clock.advance(305.0)
+        should_stop, reason, _ = ctrl.check(4321)
+        self.assertTrue(should_stop)
+        self.assertEqual(reason, "idle_timeout")
+
+    def test_ps_failure_fails_closed(self) -> None:
+        live_pgid = os.getpgrp()
+        wd = ProcessWatchdog(ps_timeout_s=0.05)
+        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["ps"], timeout=0.05)):
+            metrics = wd.sample(live_pgid)
+        self.assertTrue(metrics.ps_degraded)
+        self.assertFalse(metrics.has_progress)
+
+        clock = _FakeClock(2000.0)
+        ctrl = AdaptiveTimeoutController(
+            idle_timeout_s=300.0,
+            safety_cap_s=3600.0,
+            watchdog=_StubWatchdog(metrics),
+            watchdog_enabled=True,
+            clock=clock,
+        )
+        ctrl.register_pgid(live_pgid)
+        clock.advance(301.0)
+        should_stop, reason, _ = ctrl.check(live_pgid)
+        self.assertTrue(should_stop)
+        self.assertEqual(reason, "idle_timeout")
+
+    def test_hard_safety_cap_3600s_unconditional(self) -> None:
+        clock = _FakeClock(5000.0)
+        active_metrics = WatchdogMetrics(
+            pgid=5555,
+            alive=True,
+            descendant_pids=(5555,),
+            new_descendants=(5556,),
+            cpu_time_s=100.0,
+            cpu_delta_s=5.0,
+            ps_degraded=False,
+        )
+        ctrl = AdaptiveTimeoutController(
+            idle_timeout_s=300.0,
+            safety_cap_s=3600.0,
+            watchdog=_StubWatchdog(active_metrics),
+            watchdog_enabled=True,
+            clock=clock,
+        )
+        ctrl.register_pgid(5555)
+        clock.advance(3601.0)
+        ctrl.record_activity("stdout")
+        should_stop, reason, _ = ctrl.check(5555)
+        self.assertTrue(should_stop)
+        self.assertEqual(reason, "absolute_cap")
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/tests/test_detached_turn_execution.py b/tests/test_detached_turn_execution.py
new file mode 100644
index 0000000..978cac7
--- /dev/null
+++ b/tests/test_detached_turn_execution.py
@@ -0,0 +1,126 @@
+import os
+import tempfile
+import unittest
+from pathlib import Path
+
+from core.backend_adapter import ToolCall, ToolFunction, TurnResult, Usage
+from core.turn_session_manager import TurnForbiddenError, TurnSessionManager
+
+
+class DetachedTurnExecutionTests(unittest.TestCase):
+    def setUp(self) -> None:
+        self._tmp = tempfile.TemporaryDirectory()
+        self._state_dir = self._tmp.name
+
+    def tearDown(self) -> None:
+        self._tmp.cleanup()
+
+    def test_client_disconnect_detaches_and_finishes_in_background(self) -> None:
+        manager = TurnSessionManager(state_root=self._state_dir)
+        turn, existing = manager.create_or_attach_turn(
+            model="claude-4.6-opus",
+            backend="droid",
+            cwd="/tmp",
+            messages=[{"role": "user", "content": "hello"}],
+            session_id="sess-01",
+            owner_token_hash="owner-a",
+            requested_turn_id="turn-detach-01",
+            stream=True,
+        )
+        self.assertFalse(existing)
+        self.assertEqual(turn.status, "RUNNING_ATTACHED")
+
+        turn.buffer.append("content", "Hello ")
+        turn.mark_detached()
+        self.assertEqual(turn.status, "RUNNING_DETACHED")
+
+        turn.buffer.append("content", "world!")
+        result = TurnResult(
+            state="done",
+            rc=0,
+            text="Hello world!",
+            reasoning="step-by-step",
+            usage=Usage(input_tokens=12, output_tokens=6),
+            tool_calls=(
+                ToolCall(
+                    index=0,
+                    id="call-1",
+                    function=ToolFunction(name="read_file", arguments='{"path":"a.py"}'),
+                ),
+            ),
+        )
+        manager.complete_turn_from_result(turn, result, backend_kind="droid")
+
+        snap = manager.get_turn_snapshot("turn-detach-01", owner_token_hash="owner-a")
+        self.assertEqual(snap["schema_version"], "1.0")
+        self.assertEqual(snap["status"], "completed")
+        self.assertEqual(snap["state"], "COMPLETED")
+        self.assertEqual(snap["content"], "Hello world!")
+        self.assertEqual(snap["reasoning_content"], "step-by-step")
+        self.assertEqual(len(snap["tool_calls"]), 1)
+        self.assertEqual(snap["usage"]["prompt_tokens"], 12)
+        self.assertEqual(snap["usage"]["completion_tokens"], 6)
+
+        turn_file = Path(self._state_dir) / "turns" / "turn-detach-01.json"
+        self.assertTrue(turn_file.exists())
+        mode = os.stat(turn_file).st_mode & 0o777
+        self.assertEqual(mode, 0o600)
+
+    def test_idempotent_retry_and_resume_turn_id(self) -> None:
+        manager = TurnSessionManager(state_root=self._state_dir)
+        t1, ex1 = manager.create_or_attach_turn(
+            model="claude-4.6-opus",
+            backend="droid",
+            cwd="/tmp",
+            messages=[{"role": "user", "content": "retry-test"}],
+            session_id="sess-02",
+            owner_token_hash="owner-a",
+            requested_turn_id="turn-idem-01",
+            stream=True,
+        )
+        self.assertFalse(ex1)
+
+        t2, ex2 = manager.create_or_attach_turn(
+            model="claude-4.6-opus",
+            backend="droid",
+            cwd="/tmp",
+            messages=[{"role": "user", "content": "retry-test"}],
+            session_id="sess-02",
+            owner_token_hash="owner-a",
+            requested_turn_id="turn-idem-01",
+            stream=True,
+        )
+        self.assertTrue(ex2)
+        self.assertIs(t1, t2)
+
+        t3, ex3 = manager.create_or_attach_turn(
+            model="claude-4.6-opus",
+            backend="droid",
+            cwd="/tmp",
+            messages=[{"role": "user", "content": "retry-test"}],
+            session_id="sess-02",
+            owner_token_hash="owner-a",
+            resume_turn_id="turn-idem-01",
+            stream=True,
+        )
+        self.assertTrue(ex3)
+        self.assertIs(t1, t3)
+
+    def test_owner_isolation_enforced(self) -> None:
+        manager = TurnSessionManager(state_root=self._state_dir)
+        manager.create_or_attach_turn(
+            model="claude-4.6-opus",
+            backend="droid",
+            cwd="/tmp",
+            messages=[{"role": "user", "content": "secret"}],
+            session_id="sess-03",
+            owner_token_hash="owner-a",
+            requested_turn_id="turn-own-01",
+            stream=False,
+        )
+        with self.assertRaises(TurnForbiddenError):
+            manager.get_turn_snapshot("turn-own-01", owner_token_hash="owner-b")
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/tests/test_dsh_profile_config.py b/tests/test_dsh_profile_config.py
new file mode 100644
index 0000000..0a3df77
--- /dev/null
+++ b/tests/test_dsh_profile_config.py
@@ -0,0 +1,19 @@
+from __future__ import annotations
+
+import unittest
+from pathlib import Path
+
+
+class DshProfileConfigTests(unittest.TestCase):
+    def test_cordis_patch_yml_persona_suffix_does_not_contain_volatile_cwd(self) -> None:
+        patch_path = Path.home() / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
+        if not patch_path.exists():
+            self.skipTest(f"{patch_path} is not present on this machine")
+
+        content = patch_path.read_text(encoding="utf-8")
+        self.assertIn("id: deployment:persona-suffix", content)
+        self.assertNotIn("{{cwd}}", content, "cordis.patch.yml must not inject volatile {{cwd}} into persona-suffix")
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/tests/test_graceful_shutdown_drain.py b/tests/test_graceful_shutdown_drain.py
new file mode 100644
index 0000000..1bac62a
--- /dev/null
+++ b/tests/test_graceful_shutdown_drain.py
@@ -0,0 +1,106 @@
+import signal
+import subprocess
+import tempfile
+import unittest
+
+from core.lifecycle import DrainState, HubLifecycleManager, KeepaliveController
+from core.turn_session_manager import TurnSessionManager
+
+
+class GracefulShutdownDrainTests(unittest.TestCase):
+    def setUp(self) -> None:
+        self._tmp = tempfile.TemporaryDirectory()
+        self._state_dir = self._tmp.name
+
+    def tearDown(self) -> None:
+        self._tmp.cleanup()
+
+    def test_signal_handler_only_sets_event_and_admission_returns_503(self) -> None:
+        manager = TurnSessionManager(state_root=self._state_dir)
+        lifecycle = HubLifecycleManager(
+            state_dir=self._state_dir,
+            turn_manager=manager,
+            drain_timeout_s=2.0,
+            retry_after_s=5,
+        )
+        self.assertFalse(lifecycle.is_draining())
+
+        lifecycle.handle_signal(signal.SIGTERM, None)
+        self.assertTrue(lifecycle.shutdown_requested.is_set())
+        self.assertTrue(lifecycle.is_draining())
+
+        code, headers, body = lifecycle.draining_response()
+        self.assertEqual(code, 503)
+        self.assertEqual(headers.get("Retry-After"), "5")
+        self.assertEqual(headers.get("X-Bridge-Draining"), "true")
+        self.assertEqual(body["error"]["code"], 503)
+        self.assertEqual(body["error"]["type"], "overloaded")
+        self.assertEqual(lifecycle.health_headers().get("X-Bridge-Draining"), "true")
+
+    def test_drain_waits_for_active_turn_and_persists_interrupted_on_timeout(self) -> None:
+        manager = TurnSessionManager(state_root=self._state_dir)
+        turn, _ = manager.create_or_attach_turn(
+            model="claude-4.6-opus",
+            backend="droid",
+            cwd="/tmp",
+            messages=[{"role": "user", "content": "long-turn"}],
+            session_id="sess-drain",
+            owner_token_hash="owner-1",
+            requested_turn_id="turn-drain-01",
+            stream=True,
+        )
+        turn.buffer.append("content", "partial output")
+
+        lifecycle = HubLifecycleManager(
+            state_dir=self._state_dir,
+            turn_manager=manager,
+            drain_timeout_s=0.1,
+            retry_after_s=5,
+        )
+        lifecycle.handle_signal(signal.SIGTERM, None)
+        summary = lifecycle.run_drain_once()
+
+        self.assertEqual(lifecycle.state, DrainState.STOPPED)
+        self.assertIn("turn-drain-01", summary["interrupted_turn_ids"])
+
+        snap = manager.get_turn_snapshot("turn-drain-01", owner_token_hash="owner-1")
+        self.assertEqual(snap["status"], "interrupted_drain")
+        self.assertEqual(snap["content"], "partial output")
+        self.assertEqual(snap["error"]["code"], "drain_timeout")
+
+    def test_startup_orphan_reaper_cleans_children_json(self) -> None:
+        manager = TurnSessionManager(state_root=self._state_dir)
+        proc = subprocess.Popen(
+            ["python3", "-c", "import time; time.sleep(60)"],
+            start_new_session=True,
+        )
+        try:
+            manager.register_child_pgid(
+                "turn-orphan-01",
+                proc.pid,
+                pid=proc.pid,
+                command="python3 -c import time; time.sleep(60)",
+            )
+            lifecycle = HubLifecycleManager(
+                state_dir=self._state_dir,
+                turn_manager=manager,
+                orphan_grace_s=0.2,
+            )
+            reaped = lifecycle.reap_orphans_on_startup()
+            self.assertIn(proc.pid, reaped)
+            proc.wait(timeout=3.0)
+            self.assertIsNotNone(proc.returncode)
+        finally:
+            if proc.poll() is None:
+                proc.kill()
+                proc.wait(timeout=2.0)
+
+    def test_keepalive_clamped_to_10s(self) -> None:
+        ka = KeepaliveController(max_interval_s=10.0)
+        self.assertEqual(ka.effective_interval(15.0), 10.0)
+        self.assertEqual(ka.effective_interval(5.0), 5.0)
+        self.assertTrue(ka.sse_comment().startswith(": keepalive"))
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/tests/test_muse_bridge_killpg.py b/tests/test_muse_bridge_killpg.py
index 7538209..53147b3 100644
--- a/tests/test_muse_bridge_killpg.py
+++ b/tests/test_muse_bridge_killpg.py
@@ -3437,7 +3437,15 @@ class ApprovalTest(_BridgeScenario):
         with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "100"}):
             with self.assertRaises(Exception):
                 load_bridge()
-        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "1800"}):
+        # Дефолт без переопределения: потолок хода и запроса — 60 минут.
+        env_wo_timeout = {
+            k: v for k, v in os.environ.items() if k != "MUSE_BRIDGE_TIMEOUT_S"
+        }
+        with mock.patch.dict(os.environ, env_wo_timeout, clear=True):
+            default_mod = load_bridge()
+        self.assertEqual(default_mod.TIMEOUT_S, 3600.0)
+        self.assertEqual(default_mod.REQUEST_CAP_S, 3600.0)
+        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "3600"}):
             self.assertIsNotNone(load_bridge())
 
 
diff --git a/tests/test_turn_cancel_and_gap.py b/tests/test_turn_cancel_and_gap.py
new file mode 100644
index 0000000..19ee9bd
--- /dev/null
+++ b/tests/test_turn_cancel_and_gap.py
@@ -0,0 +1,88 @@
+import subprocess
+import tempfile
+import unittest
+
+from core.turn_session_manager import (
+    GapDetectedError,
+    TurnBuffer,
+    TurnSessionManager,
+    validate_turn_id,
+)
+
+
+class TurnCancelAndGapTests(unittest.TestCase):
+    def setUp(self) -> None:
+        self._tmp = tempfile.TemporaryDirectory()
+        self._state_dir = self._tmp.name
+
+    def tearDown(self) -> None:
+        self._tmp.cleanup()
+
+    def test_delete_turn_cancels_tree_and_releases_slot_exactly_once(self) -> None:
+        release_calls: list[int] = []
+        manager = TurnSessionManager(state_root=self._state_dir, cancel_grace_s=0.2)
+        proc = subprocess.Popen(
+            ["python3", "-c", "import time; time.sleep(60)"],
+            start_new_session=True,
+        )
+        try:
+            turn, _ = manager.create_or_attach_turn(
+                model="claude-4.6-opus",
+                backend="droid",
+                cwd="/tmp",
+                messages=[{"role": "user", "content": "cancel me"}],
+                session_id="sess-cancel",
+                owner_token_hash="owner-1",
+                requested_turn_id="turn-cancel-01",
+                stream=True,
+                slot_release_fn=lambda: release_calls.append(1),
+            )
+            manager.register_child_pgid(
+                "turn-cancel-01",
+                proc.pid,
+                pid=proc.pid,
+                command="python3 -c import time; time.sleep(60)",
+            )
+
+            cancelled = manager.cancel_turn("turn-cancel-01", owner_token_hash="owner-1")
+            self.assertEqual(cancelled.status, "CANCELLED")
+            proc.wait(timeout=3.0)
+            self.assertIsNotNone(proc.returncode)
+
+            # Second cancel and manual slot release must be idempotent no-ops
+            manager.cancel_turn("turn-cancel-01", owner_token_hash="owner-1")
+            turn.release_slot_once()
+            self.assertEqual(len(release_calls), 1)
+        finally:
+            if proc.poll() is None:
+                proc.kill()
+                proc.wait(timeout=2.0)
+
+    def test_ring_buffer_overflow_returns_410_gap_detected(self) -> None:
+        buf = TurnBuffer(max_bytes=64)
+        for idx in range(10):
+            buf.append("content", f"chunk-{idx:02d}-0123456789\n")
+
+        self.assertGreater(buf.oldest_available_seq, 1)
+        self.assertEqual(buf.last_seq, 10)
+
+        with self.assertRaises(GapDetectedError) as ctx:
+            buf.events_since(0, turn_id="turn-gap-01")
+
+        payload = ctx.exception.to_http_payload()
+        self.assertEqual(payload["error"]["code"], "GAP_DETECTED")
+        self.assertEqual(payload["error"]["turn_id"], "turn-gap-01")
+        self.assertEqual(payload["error"]["requested_from_seq"], 0)
+        self.assertEqual(payload["error"]["oldest_available_seq"], buf.oldest_available_seq)
+        self.assertEqual(payload["error"]["last_seq"], 10)
+
+    def test_validate_turn_id_rejects_traversal(self) -> None:
+        self.assertTrue(validate_turn_id("turn_123-abc"))
+        self.assertFalse(validate_turn_id("../etc/passwd"))
+        self.assertFalse(validate_turn_id("a/b"))
+        self.assertFalse(validate_turn_id(""))
+        self.assertFalse(validate_turn_id("x" * 65))
+
+
+if __name__ == "__main__":
+    unittest.main()

```

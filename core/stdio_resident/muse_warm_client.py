"""Warm stdio MSP v1 клиент Muse (VER-008, AD-004/AD-006; флаг default false)."""
from __future__ import annotations

import copy, json, math, os, select, subprocess, threading, time
from collections.abc import Callable, Mapping
from typing import Any

from core.runtime_env import env_bool

WARM_FLAG = "MUSE_WARM_MSP_STDIO_ENABLED"
RETRYABLE_MSP_CODES = frozenset({-32001, -32031})
_WRAPPER_ENV, _TIMEOUT_ENV = "MUSE_CLI_WRAPPER", "MUSE_WARM_STDIO_TIMEOUT_S"
_WRAPPER_SUFFIX = ".config/muse-launch/muse-cli.sh"
_DEFAULT_TIMEOUT_S = 30.0
TransportFactory = Callable[[], Any]
NotificationHandler = Callable[[str, dict[str, Any]], bool]

class MspError(Exception):
    """Ошибка MSP-пира с числовым кодом JSON-RPC."""
    def __init__(self, code: int, message: str = "") -> None:
        super().__init__(message or f"msp_error:{code}")
        self.code, self.message = int(code), str(message)
def warm_stdio_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return env_bool(os.environ if environ is None else environ, (WARM_FLAG,), False)
def is_retryable_msp_error(code: int | MspError) -> bool:
    value = code.code if isinstance(code, MspError) else code
    return isinstance(value, int) and value in RETRYABLE_MSP_CODES
def resolve_wrapper_path(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    override, home = env.get(_WRAPPER_ENV, "").strip(), env.get("HOME", "").strip()
    return override or (os.path.join(home, _WRAPPER_SUFFIX) if home else os.path.expanduser(f"~/{_WRAPPER_SUFFIX}"))

def _uuid7() -> str:
    """RFC 9562 UUIDv7 для commandId в MSP v1."""
    ms = (time.time_ns() // 1_000_000).to_bytes(6, "big")
    rnd = bytearray(os.urandom(10))
    rnd[0], rnd[2] = (rnd[0] & 0x0F) | 0x70, (rnd[2] & 0x3F) | 0x80
    h = (ms + bytes(rnd)).hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

def build_serve_argv(wrapper_path: Any = None, environ: Mapping[str, str] | None = None) -> list[str]:
    if isinstance(wrapper_path, Mapping): wrapper_path, environ = None, wrapper_path
    return [str(wrapper_path) if wrapper_path else resolve_wrapper_path(environ), "serve", "--listen", "--allow-session-posture", "--vacate-on-upgrade"]
def build_stdio_serve_argv(wrapper_path: Any = None, environ: Mapping[str, str] | None = None) -> list[str]:
    if isinstance(wrapper_path, Mapping): wrapper_path, environ = None, wrapper_path
    return [str(wrapper_path) if wrapper_path else resolve_wrapper_path(environ), "serve"]
def decide_muse_transport(probe_error_code: str | None = None, *, output_schema: bool = False, environ: Mapping[str, str] | None = None) -> str:
    if output_schema: return "exec"
    env = os.environ if environ is None else environ
    if probe_error_code is None and env_bool(env, ("MUSE_UNIX_SOCKET_PROBE_ENABLED",), False): return "unix_socket"
    return "warm_stdio" if warm_stdio_enabled(env) else "legacy"

def _timeout_s(environ: Mapping[str, str]) -> float:
    try:
        value = float(environ.get(_TIMEOUT_ENV, ""))
    except ValueError:
        return _DEFAULT_TIMEOUT_S
    return value if math.isfinite(value) and value > 0 else _DEFAULT_TIMEOUT_S

class _StdioMspTransport:
    """Небуферизованный бинарный NDJSON JSON-RPC поверх stdio ``muse serve`` с общим deadline."""
    def __init__(self, argv: list[str], on_notification: NotificationHandler, timeout_s: float) -> None:
        self._on_notification, self._timeout_s = on_notification, timeout_s
        self._next_id, self._lock, self._buf = 0, threading.Lock(), bytearray()
        self._proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        if self._proc.stdin is not None: os.set_blocking(self._proc.stdin.fileno(), False)
    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self._next_id += 1
            deadline = time.monotonic() + self._timeout_s
            self._send({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}}, deadline)
            return self._read_result(self._next_id, deadline)
    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        with self._lock:
            payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
            if params is not None: payload["params"] = params
            self._send(payload, time.monotonic() + self._timeout_s)
    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(timeout=self._timeout_s)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                try: self._proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired: pass
    def _send(self, payload: dict[str, Any], deadline: float) -> None:
        if self._proc.stdin is None: raise MspError(-32001, "msp stdin closed")
        fd, view = self._proc.stdin.fileno(), memoryview((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        while view:
            rem = deadline - time.monotonic()
            if rem <= 0 or not select.select([], [fd], [], rem)[1]:
                raise MspError(-32001, "msp stdin write timeout")
            try: written = os.write(fd, view)
            except BlockingIOError: continue
            except OSError as exc: raise MspError(-32001, f"msp stdin closed: {exc}") from exc
            if written <= 0: raise MspError(-32001, "msp stdin closed")
            view = view[written:]
    def _read_line(self, fd: int, deadline: float) -> str:
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                raw = bytes(self._buf[:nl + 1]); del self._buf[:nl + 1]
                try: return raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError: return ""
            rem = deadline - time.monotonic()
            if rem <= 0 or not select.select([fd], [], [], rem)[0]:
                raise MspError(-32001, "msp response timeout/EOF")
            chunk = os.read(fd, 4096)
            if not chunk: raise MspError(-32001, "msp response timeout/EOF")
            self._buf.extend(chunk)
    def _read_result(self, request_id: int, deadline: float) -> dict[str, Any]:
        if self._proc.stdout is None: raise MspError(-32001, "msp stdout closed")
        fd = self._proc.stdout.fileno()
        while True:
            result = self._dispatch_line(self._read_line(fd, deadline), request_id)
            if result is not None: return result
    def _maybe_notify(self, parsed: dict[str, Any]) -> None:
        method, params = parsed.get("method"), parsed.get("params")
        if isinstance(method, str) and isinstance(params, dict): self._on_notification(method, params)
    def _raise_rpc_error(self, parsed: dict[str, Any]) -> None:
        err = parsed["error"]
        if not isinstance(err, dict) or "result" in parsed: raise MspError(-32603, "invalid jsonrpc error envelope")
        code = err.get("code", -32000)
        raise MspError(code if type(code) is int else -32000, str(err.get("message", "")))
    def _dispatch_line(self, line: str, request_id: int) -> dict[str, Any] | None:
        try: parsed = json.loads(line)
        except ValueError: return None
        if not isinstance(parsed, dict) or parsed.get("jsonrpc") != "2.0": return None
        if "id" not in parsed:
            self._maybe_notify(parsed)
            return None
        msg_id = parsed.get("id")
        if type(msg_id) is not int or msg_id != request_id: return None
        if "error" in parsed: self._raise_rpc_error(parsed)
        if not isinstance(parsed.get("result"), dict): raise MspError(-32603, "invalid jsonrpc result")
        return parsed["result"]

class MuseWarmStdioRegistry:
    """Единственный владелец состояния warm stdio: транспорт, сессии, usage."""
    def __init__(self, transport_factory: TransportFactory | None = None, *, wrapper_path: str | None = None, environ: Mapping[str, str] | None = None) -> None:
        self._transport_factory, self._wrapper_path = transport_factory, wrapper_path
        self._environ, self._transport, self._initialized = (os.environ if environ is None else environ), None, False
        self._sessions: dict[str, dict[str, Any]] = {}
        self._last_usage: dict[str, Any] = {}
        self._lock = threading.RLock()
    def acquire_session(self, session_id: str, model_id: str | None = None, posture: str | None = None) -> dict[str, Any]:
        """Ленивый ``initialize`` (один раз) + ``session/start``, ``developerPrompt: null``."""
        with self._lock:
            if session_id in self._sessions:
                return dict(self._sessions[session_id])
            params: dict[str, Any] = {
                "commandId": _uuid7(),
                "sessionId": session_id,
                "modelId": model_id or "muse-wonder-1.0",
                "approvalMode": posture or "denyUnmatched",
                "config": {"developerPrompt": None},
            }
            if posture:
                params["posture"] = posture
            result = self._request("session/start", params)
            self._sessions[session_id] = dict(result)
            return dict(result)
    def run_turn(self, session_id: str, text: Any = "", effort: str | None = None) -> dict[str, Any]:
        """``turn/start``; retryable MSP-ошибка повторяется ровно один раз."""
        user_input = text if isinstance(text, list) else [{"type": "text", "text": str(text)}]
        params: dict[str, Any] = {"commandId": _uuid7(), "sessionId": session_id, "input": user_input}
        if effort:
            params["reasoningEffort"] = effort
            params["effort"] = effort
        return self._request("turn/start", params, retry_once=True)
    def cancel_turn(self, session_id: str) -> dict[str, Any]:
        return self._request("turn/cancel", {"sessionId": session_id})
    def read_usage(self, session_id: str | None = None) -> dict[str, Any]:
        result = self._request("usage/read", {"sessionId": session_id} if session_id else {})
        with self._lock:
            self._last_usage = copy.deepcopy(result)
        return copy.deepcopy(result)
    def handle_notification(self, method: str, params: dict[str, Any] | None = None) -> bool:
        if method != "usage/changed":
            return False
        with self._lock:
            self._last_usage = copy.deepcopy(params or {})
        return True
    def last_usage(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._last_usage)
    def leave_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                return {}
        try:
            return self._request("session/leave", {"commandId": _uuid7(), "sessionId": session_id, "stop": True})
        finally:
            with self._lock:
                self._sessions.pop(session_id, None)
    def active_sessions(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._sessions)
    def vacate(self) -> None:
        """Drain при ``--vacate-on-upgrade``: leave всех сессий, закрытие транспорта."""
        for session_id in self.active_sessions():
            try:
                self.leave_session(session_id)
            except Exception:
                continue
        with self._lock:
            self._sessions.clear()
            transport, self._transport, self._initialized = self._transport, None, False
        close = getattr(transport, "close", None)
        if callable(close):
            close()
    def _ensure_initialized(self) -> None:
        if self._transport is None:
            if self._transport_factory is not None:
                self._transport = self._transport_factory()
            else:
                argv = build_stdio_serve_argv(self._wrapper_path, self._environ)
                self._transport = _StdioMspTransport(argv, self.handle_notification, _timeout_s(self._environ))
        if not self._initialized:
            self._transport.request("initialize", {"compatibilityEpoch": 0, "clientInfo": {"name": "cli_agent_bridge", "version": "1.0"}})
            notify = getattr(self._transport, "notify", None)
            if callable(notify):
                notify("initialized")
            self._initialized = True
    def _request(self, method: str, params: dict[str, Any], retry_once: bool = False) -> dict[str, Any]:
        with self._lock:
            self._ensure_initialized()
            try:
                return self._transport.request(method, params)
            except MspError as exc:
                if retry_once and is_retryable_msp_error(exc):
                    return self._transport.request(method, params)
                raise

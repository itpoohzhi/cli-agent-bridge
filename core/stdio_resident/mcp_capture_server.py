"""Loopback HTTP MCP server and turn-scoped wire session (BND-002, M-MOD-I4)."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar, cast, final, override

from core.stdio_resident.mcp_tool_capture import McpToolCaptureSession


@dataclass(frozen=True, slots=True)
class TurnMcpSessionSpec:
    """Turn-scoped MCP and host-tool configuration (secrets redacted in repr)."""

    mcp_url: str | None = None
    bearer_token: str | None = None
    server_name: str = "bridge"
    developer_prompt: str | None = None
    suppress_host_tools: bool = False
    emulate_tools: bool = False
    clean_cli_home: bool = False

    @override
    def __repr__(self) -> str:
        return (
            f"TurnMcpSessionSpec(mcp_url=<redacted>, bearer_token=<redacted>, server_name={self.server_name!r}, "
            f"suppress_host_tools={self.suppress_host_tools!r}, emulate_tools={self.emulate_tools!r}, clean_cli_home={self.clean_cli_home!r})"
        )


class TurnWireSessionScope:
    """Single owner of turn-scoped MCP metadata and cancel payload builder."""

    _var: ClassVar[ContextVar[TurnWireSessionScope | None]] = ContextVar("turn_wire_session_scope", default=None)

    def __init__(self, spec: TurnMcpSessionSpec) -> None:
        self.spec: TurnMcpSessionSpec = spec
        self._cancel_builder: Callable[[Mapping[str, object]], bytes | None] | None = None

    def register_cancel_builder(self, builder: Callable[[Mapping[str, object]], bytes | None]) -> None:
        """Register a turn-scoped cancel payload builder from the driver."""
        self._cancel_builder = builder

    def build_cancel_payload(self, turn_context: Mapping[str, object] | None = None) -> bytes | None:
        """Build a cancel payload if a turn-scoped builder was registered."""
        if self._cancel_builder is None:
            return None
        return self._cancel_builder(turn_context if turn_context is not None else {})

    @classmethod
    def current(cls) -> TurnWireSessionScope | None:
        """Return the active turn wire scope, if any."""
        return cls._var.get()

    @classmethod
    @contextmanager
    def bind(cls, spec: TurnMcpSessionSpec) -> Generator[TurnWireSessionScope]:
        """Bind a new scope to the current context for the duration of a turn."""
        scope = cls(spec)
        token = cls._var.set(scope)
        try:
            yield scope
        finally:
            cls._var.reset(token)


@final
class _LoopbackHttpServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def _make_handler(owner: McpLoopbackServer) -> type[BaseHTTPRequestHandler]:
    class _McpHandler(BaseHTTPRequestHandler):
        @override
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _write_response(self, status: int, payload: bytes | None = None) -> None:
            self.send_response(status)
            if payload is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)) if payload is not None else "0")
            self.send_header("Connection", "close")
            self.end_headers()
            if payload is not None:
                _ = self.wfile.write(payload)

        def _write_json(self, status: int, body: Mapping[str, object]) -> None:
            self._write_response(status, json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        def _read_json_payload(self) -> dict[str, object] | None:
            raw_len = self.headers.get("Content-Length")
            try:
                content_len = int(raw_len) if raw_len is not None else -1
            except ValueError:
                content_len = -1
            if content_len < 0 or content_len > owner.max_request_bytes:
                self._write_json(413, {"error": "payload too large"})
                return None
            raw_body = self.rfile.read(content_len)
            try:
                parsed = cast(object, json.loads(raw_body.decode("utf-8"))) if len(raw_body) == content_len else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            if not isinstance(parsed, dict):
                self._write_json(400, {"error": "invalid json payload"})
                return None
            return cast(dict[str, object], parsed)

        def do_POST(self) -> None:  # noqa: N802
            ok, status = owner.session.verify_auth(self.path, self.headers.get("Authorization"))
            if not ok:
                self._write_response(status)
                return
            payload = self._read_json_payload()
            if payload is None:
                return
            resp = owner.session.handle_rpc_request(payload)
            if resp.captured_tool_call:
                owner.captured_event.set()
                _ = owner.wait_for_release()
            if resp.body is None:
                self._write_response(resp.http_status)
            else:
                self._write_json(resp.http_status, cast(Mapping[str, object], resp.body))

    return _McpHandler


class McpLoopbackServer:
    """Ephemeral 127.0.0.1 HTTP loopback server for MCP tool-call capture."""

    def __init__(
        self, session: McpToolCaptureSession, *, max_request_bytes: int = 1048576, cancel_wait_s: float = 2.0, coalesce_ms: int = 25
    ) -> None:
        self._session: McpToolCaptureSession = session
        self._max_request_bytes: int = max(1, max_request_bytes)
        self._cancel_wait_s: float = max(0.0, cancel_wait_s)
        self._coalesce_ms: int = max(0, coalesce_ms)
        self._captured_event: threading.Event = threading.Event()
        self._release_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int = 0

    @property
    def session(self) -> McpToolCaptureSession:
        return self._session

    @property
    def cancel_wait_s(self) -> float:
        return self._cancel_wait_s

    @property
    def max_request_bytes(self) -> int:
        return self._max_request_bytes

    @property
    def port(self) -> int:
        return self._port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}{self._session.spec.capability_path}"

    @property
    def captured_event(self) -> threading.Event:
        return self._captured_event

    def release(self) -> None:
        """Release any handler threads waiting at the tool-capture barrier."""
        self._release_event.set()

    def wait_for_release(self) -> bool:
        """Wait for release signal up to cancel_wait_s."""
        return self._release_event.wait(timeout=self._cancel_wait_s)

    def wait_for_coalesce(self) -> None:
        """Sleep briefly to coalesce concurrent tools/call requests."""
        if self._coalesce_ms > 0:
            time.sleep(self._coalesce_ms / 1000.0)

    def start(self) -> McpLoopbackServer:
        """Bind loopback port 0 and start serving in a daemon thread."""
        with self._lock:
            if self._httpd is not None:
                return self
            httpd = _LoopbackHttpServer(("127.0.0.1", 0), _make_handler(self))
            self._port = int(httpd.server_address[1])
            thread = threading.Thread(target=httpd.serve_forever, name="mcp-loopback", daemon=True)
            self._httpd, self._thread = httpd, thread
            thread.start()
        return self

    def close(self) -> None:
        """Idempotently release barriers, shut down HTTP server, and join thread."""
        self._release_event.set()
        with self._lock:
            httpd, thread = self._httpd, self._thread
            self._httpd, self._thread = None, None
        if httpd is not None:
            with suppress(Exception):
                httpd.shutdown()
                httpd.server_close()
        if thread is not None:
            with suppress(Exception):
                thread.join(timeout=2.0)

    def __enter__(self) -> McpLoopbackServer:
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @override
    def __repr__(self) -> str:
        return f"McpLoopbackServer(port={self._port}, server_name={self._session.spec.server_name!r}, url=<redacted>)"

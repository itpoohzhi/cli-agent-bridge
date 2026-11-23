"""Meta Muse MSP v1 protocol driver for resident stdio processes."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import os
import select
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar

from adapters.stdio_drivers.muse_codec import (
    MuseDecodedChunk, build_initialize_msg, build_initialized_msg, build_session_leave_msg,
    build_session_start_msg, build_turn_start_msg, decode_msp_line, is_uuid7, uuid7,
)
from adapters.stdio_drivers.muse_env import (
    build_muse_env,
    build_muse_zero_canon_argv,
    build_muse_zero_canon_env,
    compute_muse_fingerprint,
    get_fingerprint_field,
    resolve_pinned_path,
    verify_binary,
)
from core.stdio_resident.process_io import StdioIoError
from core.stdio_resident.protocol_driver import DecodedChunk, DriverCapabilities, StdioProtocolDriver
from core.stdio_resident.rpc_drivers import register_protocol_driver

_DEFAULT_SANDBOX_FLAGS: tuple[str, ...] = ("--sandbox",)
_DEFAULT_CLI_ARGS: tuple[str, ...] = ("--stdio",)
_MUSE_SERVE_ARGS: tuple[str, ...] = (
    "serve", "--provider", "meta", "--disable-write", "--disable-shell", "--disable-request-user-input", "--no-session-log",
)


class MuseMspDriver(StdioProtocolDriver):
    """StdioProtocolDriver implementation for Meta Muse MSP v1 (``msp-v1``)."""

    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        protocol_name="msp-v1", supports_soft_cancel=False, supports_multi_turn=True,
    )

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = dict(config or {})
        self._next_id: int = 1
        self._id_lock = threading.Lock()
        self._last_session_id: str | None = None

    @property
    def capabilities(self) -> DriverCapabilities:
        return self._capabilities

    def _allocate_id(self) -> int:
        with self._id_lock:
            req_id = self._next_id
            self._next_id += 1
            return req_id

    @staticmethod
    def _extract_seq(source: Mapping[str, Any], keys: tuple[str, ...]) -> list[str] | None:
        for key in keys:
            val = source.get(key)
            if isinstance(val, Sequence) and not isinstance(val, str | bytes):
                return [str(arg) for arg in val]
        return None

    def _cli_args(self) -> list[str]:
        configured = self._extract_seq(self._config, ("cli_argv", "cli_args"))
        if configured is not None:
            return configured
        return list(_MUSE_SERVE_ARGS if isinstance(self._config.get("technical_ref"), Mapping) else _DEFAULT_CLI_ARGS)

    def verify_environment(self) -> tuple[bool, str]:
        """Run fail-closed SHA-256 verification of Muse wrapper and binary."""
        return verify_binary(self._config)

    def _require_verified(self) -> None:
        ok, reason = self.verify_environment()
        if not ok:
            raise RuntimeError(reason or "binary_sha256_mismatch")

    def build_sandbox_args(self) -> list[str]:
        """Return CLI sandbox flags required for the Muse resident process."""
        configured = self._extract_seq(self._config, ("sandbox_flags",))
        if configured is not None:
            return configured
        return [] if isinstance(self._config.get("technical_ref"), Mapping) else list(_DEFAULT_SANDBOX_FLAGS)

    def build_command(self) -> list[str]:
        """Build the pinned Muse wrapper command after fail-closed SHA-256 verification."""
        self._require_verified()
        raw_exec = get_fingerprint_field(self._config, "wrapper_path") or get_fingerprint_field(self._config, "binary_path")
        executable = resolve_pinned_path(raw_exec) if raw_exec else "muse-wrapper"
        return [executable, *self.build_sandbox_args(), *self._cli_args()]

    def build_argv(self, base_argv: list[str], options: Mapping[str, Any]) -> list[str]:
        """Build full argv from ``base_argv`` or ``build_command()`` plus options."""
        if not base_argv:
            return self.build_command()
        argv = list(base_argv)
        if raw_wrapper := get_fingerprint_field(self._config, "wrapper_path"):
            self._require_verified()
            pinned = resolve_pinned_path(raw_wrapper)
            argv[next((i for i, a in enumerate(argv[:2]) if a and resolve_pinned_path(a) == pinned), 0)] = pinned
        groups = [self.build_sandbox_args(), *([self._cli_args()] if isinstance(self._config.get("technical_ref"), Mapping) else [])]
        if (extra := self._extract_seq(options, ("cli_argv", "cli_args"))) is not None and extra != list(base_argv):
            groups.append(extra)
        for arg in (a for g in groups for a in g):
            if arg not in argv:
                argv.append(arg)
        return argv

    def build_env(self, base_env: Mapping[str, str], turn_sandbox: str | None = None) -> dict[str, str]:
        """Build an allowlisted environment from ``os.environ`` with pinned ``MUSE_BIN_PATH``."""
        _ = base_env
        raw_bin = get_fingerprint_field(self._config, "binary_path")
        return build_muse_env(os.environ, resolve_pinned_path(raw_bin) if raw_bin else "", turn_sandbox=turn_sandbox)

    def build_zero_canon_env(self, base_env: Mapping[str, str], root: str) -> dict[str, str]:
        """Build isolated Zero-Canon environment for Muse resident turn (trusted os.environ only)."""
        _ = base_env
        raw_bin = get_fingerprint_field(self._config, "binary_path")
        return build_muse_zero_canon_env(
            None,
            resolve_pinned_path(raw_bin) if raw_bin else "",
            root,
            server_env=os.environ,
        )

    def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
        """Append `--preset empty` for Zero-Canon Muse turns."""
        _ = (model, effort)
        return build_muse_zero_canon_argv(argv)

    def compute_fingerprint(self) -> str:
        """Compute deterministic SHA-256 fingerprint for ``SlotAffinityKey``."""
        return compute_muse_fingerprint(self._config, self.build_sandbox_args(), self._cli_args(), self.build_env(os.environ))

    def _ensure_session_id(self, turn_context: Any, create_if_missing: bool = False) -> str:
        candidates: list[Any] = []
        if isinstance(turn_context, Mapping):
            candidates.extend((turn_context.get("_msp_session_id"), turn_context.get("session_id"), turn_context.get("sessionId")))
        elif turn_context is not None:
            candidates.extend((getattr(turn_context, "_msp_session_id", None), getattr(turn_context, "session_id", None)))
        if not create_if_missing:
            candidates.extend((self._last_session_id, self._config.get("session_id")))
        session_id = next((c for c in candidates if is_uuid7(c)), None) or uuid7()
        if isinstance(turn_context, dict):
            turn_context["_msp_session_id"] = session_id
        self._last_session_id = session_id
        return session_id

    def run_handshake(self, handle: Any, turn_context: Any = None, timeout_s: float = 10.0) -> bool:
        """Run MSP v1 ``initialize`` -> ack -> ``initialized`` notification handshake."""
        _ = turn_context
        with self._id_lock:
            self._next_id = max(self._next_id, 2)
        ok = self._send_and_wait_ack(handle, build_initialize_msg(1), lambda p: p.get("id") == 1, timeout_s)
        return ok and self._write_handle(handle, build_initialized_msg())

    def prepare_turn(self, handle: Any, turn_context: Any = None, timeout_s: float = 10.0) -> bool:
        """Ensure a UUIDv7 session and run MSP v1 ``session/start`` -> ack."""
        ctx = turn_context if isinstance(turn_context, Mapping) else {}
        model_id = str(ctx.get("model_id") or ctx.get("model") or self._config.get("model_id") or self._config.get("model") or "muse-wonder-1.0")
        approval_mode = str(ctx.get("approval_mode") or self._config.get("approval_mode") or "denyUnmatched")
        req_id = self._allocate_id()
        profile_norm = str(ctx.get("review_profile") or "").strip().lower().replace("_", "-")
        is_zero_canon = profile_norm == "zero-canon" or str(ctx.get("zero_canon") or "").strip().lower() in ("1", "true")
        payload = build_session_start_msg(
            self._ensure_session_id(turn_context, True),
            model_id,
            approval_mode,
            uuid7(),
            req_id,
            clear_developer_prompt=is_zero_canon,
        )
        return self._send_and_wait_ack(handle, payload, lambda p: p.get("id") == req_id, timeout_s)

    def encode_turn(self, prompt: str, turn_context: Mapping[str, Any] | None = None) -> bytes:
        """Encode a user turn as an MSP v1 ``turn/start`` JSON-RPC line."""
        ctx = turn_context or {}
        req_id = ctx.get("request_id")
        rid = req_id if ((isinstance(req_id, int) and not isinstance(req_id, bool)) or isinstance(req_id, str)) else self._allocate_id()
        return build_turn_start_msg(self._ensure_session_id(ctx), str(ctx.get("effort") or self._config.get("effort") or "medium"), prompt, uuid7(), rid)

    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        """Decode one stdout NDJSON line, ignoring blank lines."""
        return decode_msp_line(raw_line) if raw_line.strip() else None

    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        """Return True if the line marks terminal turn completion or error."""
        d = decoded if decoded is not None else self.decode_line(raw_line)
        return bool(d and d.is_terminal)

    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        """Return True if the line marks a tool-call stop."""
        d = decoded if decoded is not None else self.decode_line(raw_line)
        return bool(d and d.is_tool_stop)

    def build_cancel_payload(self) -> bytes | None:
        """MSP v1 uses ``session/leave`` teardown instead of soft-cancel frames."""
        return None

    def perform_turn_teardown(self, handle: Any, turn_context: Any, timeout_s: float = 2.0) -> bool:
        """Send ``session/leave`` and wait fail-closed for its JSON-RPC ack."""
        req_id = self._allocate_id()
        payload = build_session_leave_msg(self._ensure_session_id(turn_context), uuid7(), request_id=req_id)
        return self._send_and_wait_ack(handle, payload, lambda p: self._is_teardown_ack(p, req_id), timeout_s)

    def _send_and_wait_ack(
        self, handle: Any, payload: bytes, match_fn: Callable[[Mapping[str, Any]], bool], timeout_s: float
    ) -> bool:
        if not self._is_handle_alive(handle) or not self._write_handle(handle, payload):
            return False
        deadline = time.monotonic() + max(timeout_s, 0.0)
        read_fn = getattr(handle, "read_line", None)
        stdout = None if callable(read_fn) else getattr(handle, "stdout", handle)
        while (remaining := deadline - time.monotonic()) > 0:
            if (line := self._read_ack_line(read_fn, stdout, remaining, callable(read_fn))) is None:
                break
            if not (stripped := line.strip()):
                continue
            is_err, parsed = self._parse_rpc_line(stripped)
            if is_err or (parsed is not None and match_fn(parsed)):
                return not is_err
        return False

    @staticmethod
    def _parse_rpc_line(line: str) -> tuple[bool, dict[str, Any] | None]:
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            return False, None
        chunk = decode_msp_line(line)
        if (isinstance(chunk, MuseDecodedChunk) and chunk.error) or (isinstance(payload, dict) and payload.get("error") is not None):
            return True, None
        return False, payload if isinstance(payload, dict) else None

    @staticmethod
    def _is_teardown_ack(payload: Mapping[str, Any], req_id: int | str) -> bool:
        return payload.get("error") is None and (
            payload.get("id") == req_id or payload.get("method") == "session.left"
            or (payload.get("id") is None and payload.get("result") is not None)
        )

    @staticmethod
    def _check_teardown_ack(line: str, req_id: int | str) -> bool | None:
        is_err, payload = MuseMspDriver._parse_rpc_line(line)
        return False if is_err else (True if payload is not None and MuseMspDriver._is_teardown_ack(payload, req_id) else None)

    @staticmethod
    def _is_handle_alive(handle: Any) -> bool:
        if handle is None:
            return False
        is_alive, poll = getattr(handle, "is_alive", None), getattr(handle, "poll", None)
        return (not callable(is_alive) or bool(is_alive())) and (not callable(poll) or poll() is None)

    def _read_ack_line(self, read_fn: Any, stdout: Any, remaining: float, use_reader: bool) -> str | None:
        if not use_reader:
            return self._read_line_with_timeout(stdout, remaining)
        try:
            tagged = read_fn(timeout_s=remaining)
        except (OSError, ValueError, RuntimeError, StdioIoError):
            return None
        return None if tagged is None else ("" if getattr(tagged, "is_stderr", False) else (tagged.line if hasattr(tagged, "line") else str(tagged)))

    @staticmethod
    def _write_handle(handle: Any, payload: bytes) -> bool:
        target = handle if callable(getattr(handle, "write", None)) else (getattr(handle, "stdin", None) or handle)
        if not callable(writer := getattr(target, "write", None)):
            return False
        try:
            try:
                writer(payload)
            except TypeError:
                writer(payload.decode("utf-8"))
            if callable(flush := getattr(target, "flush", None)):
                flush()
            return True
        except (OSError, ValueError, StdioIoError):
            return False

    @staticmethod
    def _read_line_with_timeout(stream: Any, timeout_s: float) -> str | None:
        if not callable(reader := getattr(stream, "readline", None)):
            return None
        try:
            fd = stream.fileno()
        except (AttributeError, OSError, ValueError):
            fd = None
        try:
            if isinstance(fd, int) and fd >= 0 and not select.select([fd], [], [], max(timeout_s, 0.0))[0]:
                return None
            raw = reader()
        except (OSError, ValueError):
            return None
        return None if not raw else (raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw))


register_protocol_driver("msp-v1", MuseMspDriver)

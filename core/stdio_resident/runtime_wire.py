"""Wire-protocol execution bridge between ResidentBridgeRuntime and StdioProtocolDriver."""

from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
import inspect
import logging
import os
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, suppress
from dataclasses import replace
from typing import Any, cast

from core.resident_canonical import _fail_if
from core.stdio_resident.config import StdioPoolConfig, mcp_tool_capture_enabled, suppress_builtin_tools_enabled
from core.stdio_resident.mcp_capture_server import McpLoopbackServer, TurnMcpSessionSpec, TurnWireSessionScope
from core.stdio_resident.mcp_tool_capture import McpToolCaptureSession, McpToolCaptureSpec
from core.stdio_resident.process_io import TIMEOUT
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.runtime_types import PreDispatchResidentError, ResidentStreamError, TurnTimeoutError
from core.stdio_resident.session_manager import _build_cancel_payload, _track_fsm_ids
from core.stdio_resident.terminal_reconcile import TerminalTextReconciler, should_reconcile_protocol
from core.stdio_resident.turn_deadlines import _TurnDeadlines, _resolve_deadlines
from core.timeout_ladder import ActivityKind
from core.tool_mode import ToolMode, resolve_tool_mode

logger = logging.getLogger(__name__)


def _resolve_spawn_env(driver: Any, fwd_env: Mapping[str, str], iso: Any) -> dict[str, str] | None:
    base_env = dict(os.environ)
    base_env.update(fwd_env)
    spawn_env: dict[str, str] | None = None
    if iso.active:
        spawn_env = cast(dict[str, str] | None, iso.env(base_env))
    else:
        build_env = getattr(driver, "build_env", None)
        if callable(build_env):
            built = dict(cast(Mapping[str, str], build_env(base_env, turn_sandbox=None)))
            changed = any((bool(fwd_env), bool({tuple(sorted(built.items()))} - {tuple(sorted(base_env.items()))})))
            spawn_env = built if changed else None
        elif fwd_env:
            spawn_env = dict(fwd_env)
    return spawn_env


def prepare_runtime_spec(driver: Any, envelope: Any, base_argv: list[str], iso: Any) -> tuple[list[str], str, dict[str, str] | None]:
    ver = getattr(driver, "verify_environment", None)
    if callable(ver):
        ok, reason = cast(tuple[bool, str], ver())
        _fail_if(not ok, RuntimeError(reason if reason else "driver environment verification failed"))
    sb_fn = getattr(driver, "build_sandbox_args", None)
    sb_args = list(cast(list[str], sb_fn())) if callable(sb_fn) else []
    iso_argv = list(iso.argv(list(base_argv), envelope.model, envelope.effort))
    argv = iso_argv + [f for f in sb_args if not bool({f} & set(iso_argv))]
    cwd = str(iso.cwd) if all((bool(iso.active), bool(iso.cwd))) else str(envelope.cwd_norm)
    return argv, cwd, _resolve_spawn_env(driver, envelope.fwd_env, iso)


def _read_next(handle: Any, timeout_s: float) -> tuple[str, Any]:
    fn = next((getattr(handle, a, None) for a in ("read_line_outcome", "read_stdout_line_outcome") if callable(getattr(handle, a, None))), None)
    res: tuple[str, Any] = cast(tuple[str, Any], fn(timeout_s=timeout_s)) if callable(fn) else ("", handle.read_line(timeout_s=timeout_s))
    return res


def _call_driver_stream(driver: Any, handle: Any, envelope: Any, ctx: dict[str, Any]) -> Iterator[DecodedChunk] | None:
    method = next((c for n in ("stream_turn", "execute_turn", "run_turn") if callable(c := getattr(driver, n, None))), None)
    out: Iterator[DecodedChunk] | None = None
    if method:
        params = inspect.signature(cast(Any, method)).parameters
        accepts_extra = any(not bool({getattr(p.kind, "name", "")} - {"VAR_KEYWORD"}) for p in params.values())
        kwargs = {k: v for k, v in ctx.items() if any((accepts_extra, bool({k} & set(params))))}
        out = cast(Iterator[DecodedChunk], cast(Any, method)(handle, envelope, **kwargs))
    return out


def teardown_driver_turn(driver: Any, handle: Any, turn_context: Mapping[str, object] | None, timeout_s: float) -> None:
    fn = getattr(driver, "perform_turn_teardown", None)
    if callable(fn):
        params = inspect.signature(cast(Any, fn)).parameters
        if not bool({len(params)} - {0, 1}):
            _ = fn(handle)
        else:
            ok = fn(handle, dict(turn_context if turn_context else {}), timeout_s=timeout_s)
            _fail_if(ok is False, ResidentStreamError("turn teardown failed", code="resident_turn_failed"))


def _run_hook(driver: Any, name: str, args: tuple[Any, ...], timeout_s: float, err_msg: str) -> None:
    fn = getattr(driver, name, None)
    ok = callable(fn)
    failed = ok and fn(*args, timeout_s=timeout_s) is False
    _fail_if(failed, PreDispatchResidentError(err_msg))


def _send_turn_input(driver: Any, handle: Any, prompt: str, turn_context: dict[str, Any], handshake_s: float) -> None:
    if not handle.generation:
        _run_hook(driver, "run_handshake", (handle,), handshake_s, "protocol_handshake_failed")
    _run_hook(driver, "prepare_turn", (handle, turn_context), handshake_s, "turn_preparation_failed")
    handle.write(driver.encode_turn(prompt, turn_context))


def _decode_tagged_line(driver: Any, handle: Any, tagged: Any, turn_ctx: dict[str, Any]) -> tuple[DecodedChunk | None, bool, bool]:
    chunk: DecodedChunk | None = None
    is_term = False
    if not getattr(tagged, "is_stderr", False):
        raw_line = tagged.line if hasattr(tagged, "line") else str(tagged)
        decoded = driver.decode_line(raw_line)
        if decoded:
            _track_fsm_ids(decoded, turn_ctx)
        err = getattr(decoded, "error", None)
        _fail_if(bool(err), RuntimeError(str(err)))
        reply = getattr(decoded, "reply_bytes", None)
        if reply:
            handle.write(reply)
        is_term = bool(driver.is_terminal(raw_line, decoded))
        chunk = DecodedChunk(is_terminal=True) if all((is_term, not decoded)) else decoded
        if is_term:
            cast(DecodedChunk, chunk).is_terminal = True
    return chunk, is_term, bool(chunk)


def build_turn_deadlines(cfg: object, ctx: Mapping[str, Any], *, now: float | None = None, environ: Mapping[str, str] | None = None) -> _TurnDeadlines:
    return _resolve_deadlines(cfg, ctx, time.monotonic() if now is None else now, environ=environ)

def _is_useful_chunk(chunk: DecodedChunk | None, is_term: bool) -> bool:
    return is_term or (chunk is not None and bool(getattr(chunk, "text", "") or getattr(chunk, "reasoning_text", "") or getattr(chunk, "tool_calls", None)))


def _read_decoded_step(
    driver: Any, handle: Any, idle_or_dl: float | _TurnDeadlines, turn_ctx: dict[str, Any], *, now_fn: Callable[[], float] = time.monotonic
) -> tuple[DecodedChunk | None, bool, bool]:
    if not isinstance(idle_or_dl, _TurnDeadlines):
        kind, tagged = _read_next(handle, idle_or_dl)
        _fail_if(kind == TIMEOUT, TurnTimeoutError("resident_turn_timeout"))
        _fail_if(isinstance(tagged, type(None)), ResidentStreamError("resident process ended before the terminal marker", code="upstream_incomplete_stream"))
        return _decode_tagged_line(driver, handle, tagged, turn_ctx)
    while True:
        rem = idle_or_dl.next_timeout(now_fn())
        kind, tagged = _read_next(handle, rem)
        idle_or_dl.next_timeout(now_fn())
        if kind == TIMEOUT:
            continue
        _fail_if(isinstance(tagged, type(None)), ResidentStreamError("resident process ended before the terminal marker", code="upstream_incomplete_stream"))
        chunk, is_term, emit = _decode_tagged_line(driver, handle, tagged, turn_ctx)
        if _is_useful_chunk(chunk, is_term):
            idle_or_dl.record_useful(now_fn(), ActivityKind.CONTENT)
        return chunk, is_term, emit


def _build_turn_mcp_context(
    envelope: Any, ctx: Mapping[str, Any]
) -> tuple[McpLoopbackServer | None, McpToolCaptureSession | None, TurnMcpSessionSpec | None]:
    if not bool(getattr(envelope, "emulate_tools", False)):
        return (None, None, None)
    cfg = ctx.get("mcp_config")
    mcp_on = bool(getattr(cfg, "mcp_tool_capture_enabled", False)) if cfg is not None else mcp_tool_capture_enabled()
    suppress_on = bool(getattr(cfg, "suppress_builtin_tools_enabled", False)) if cfg is not None else suppress_builtin_tools_enabled()
    schemas = cast(Mapping[str, Any], getattr(envelope, "tool_schemas", None) or {})
    if mcp_on and schemas and resolve_tool_mode(schemas, getattr(envelope, "tool_choice", None)) is ToolMode.EMULATE:
        cfg_eff = cfg if cfg is not None else StdioPoolConfig.from_env()
        spec_cap = McpToolCaptureSpec.create(schemas, tool_mode=ToolMode.EMULATE)
        sess = McpToolCaptureSession(spec_cap)
        srv = McpLoopbackServer(
            sess, max_request_bytes=int(getattr(cfg_eff, "mcp_max_request_bytes", 1048576)),
            cancel_wait_s=float(getattr(cfg_eff, "mcp_cancel_wait_s", 2.0)), coalesce_ms=int(getattr(cfg_eff, "mcp_coalesce_ms", 25)),
        )
        wire = TurnMcpSessionSpec(bearer_token=spec_cap.bearer_token, server_name=spec_cap.server_name, suppress_host_tools=suppress_on, emulate_tools=True)
        return (srv, sess, wire)
    return (None, None, TurnMcpSessionSpec(suppress_host_tools=True, emulate_tools=True)) if suppress_on else (None, None, None)


def _resolve_cancel_payload(driver: Any, turn_ctx: Mapping[str, object]) -> bytes | None:
    scope = TurnWireSessionScope.current()
    payload = scope.build_cancel_payload(turn_ctx) if scope is not None else None
    return payload if payload is not None else _build_cancel_payload(driver, turn_ctx)


def _drain_after_cancel(driver: Any, handle: Any, turn_ctx: dict[str, Any], wait_s: float) -> None:
    deadline = time.monotonic() + max(0.05, wait_s)
    while time.monotonic() < deadline:
        kind, tagged = _read_next(handle, min(0.05, max(0.01, deadline - time.monotonic())))
        if tagged is None and kind != TIMEOUT:
            break
        if kind == TIMEOUT or getattr(tagged, "is_stderr", False):
            continue
        raw_line = tagged.line if hasattr(tagged, "line") else str(tagged)
        decoded = None
        with suppress(Exception):
            decoded = driver.decode_line(raw_line)
        if decoded:
            _track_fsm_ids(decoded, turn_ctx)
        if driver.is_terminal(raw_line, decoded):
            break


def _finish_mcp_capture(
    driver: Any, handle: Any, turn_ctx: dict[str, Any], srv: McpLoopbackServer, *, cancel: bool = True
) -> DecodedChunk:
    srv.wait_for_coalesce()
    payload = _resolve_cancel_payload(driver, turn_ctx) if cancel else None
    if payload:
        try:
            handle.write(payload)
        except Exception as exc:
            logger.warning("resident_cancel_write_failed: %s", type(exc).__name__)
    srv.release()
    if cancel:
        _drain_after_cancel(driver, handle, turn_ctx, srv.cancel_wait_s)
    return DecodedChunk(is_terminal=True, is_tool_stop=True, tool_calls=srv.session.snapshot_captured_calls())


def _stream_with_mcp(
    driver: Any, handle: Any, turn_ctx: dict[str, Any], idle_or_dl: float | _TurnDeadlines, srv: McpLoopbackServer, *, now_fn: Callable[[], float] = time.monotonic
) -> Iterator[DecodedChunk]:
    last_activity, done = now_fn(), False
    while not done and not srv.captured_event.is_set():
        rem_idle = max(0.01, idle_or_dl.next_timeout(now_fn())) if isinstance(idle_or_dl, _TurnDeadlines) else max(0.01, idle_or_dl - (now_fn() - last_activity))
        kind, tagged = _read_next(handle, min(rem_idle, 0.05))
        if kind == TIMEOUT:
            if srv.captured_event.is_set():
                break
            idle_or_dl.next_timeout(now_fn()) if isinstance(idle_or_dl, _TurnDeadlines) else _fail_if(now_fn() - last_activity >= idle_or_dl, TurnTimeoutError("resident_turn_timeout"))
            continue
        if tagged is None:
            if srv.captured_event.is_set():
                break
            raise ResidentStreamError("resident process ended before the terminal marker", code="upstream_incomplete_stream")
        chunk, done, emit = _decode_tagged_line(driver, handle, tagged, turn_ctx)
        if isinstance(idle_or_dl, _TurnDeadlines):
            if _is_useful_chunk(chunk, done):
                idle_or_dl.record_useful(now_fn(), ActivityKind.CONTENT)
        else:
            last_activity = now_fn()
        if emit and not (done and srv.captured_event.is_set()):
            yield cast(DecodedChunk, chunk)
    if srv.captured_event.is_set():
        yield _finish_mcp_capture(driver, handle, turn_ctx, srv, cancel=not done)


def _stream_plain(
    driver: Any, handle: Any, turn_ctx: dict[str, Any], idle_or_dl: float | _TurnDeadlines, *, now_fn: Callable[[], float] = time.monotonic
) -> Iterator[DecodedChunk]:
    done = False
    while not done:
        chunk, done, emit = _read_decoded_step(driver, handle, idle_or_dl, turn_ctx, now_fn=now_fn)
        if emit:
            yield cast(DecodedChunk, chunk)


def _driver_protocol(driver: Any) -> str | None:
    proto = getattr(driver, "protocol", None)
    if not isinstance(proto, str):
        proto = getattr(getattr(driver, "capabilities", None), "protocol_name", None)
    return proto if isinstance(proto, str) else None


def _reconciled_chunks(reconciler: TerminalTextReconciler, chunks: Iterator[DecodedChunk]) -> Iterator[DecodedChunk]:
    for chunk in chunks:
        yield reconciler.apply(chunk)


def stream_driver_turn(
    driver: Any, handle: Any, envelope: Any, ctx: dict[str, Any], on_dispatched: Callable[[], None]
) -> Iterator[DecodedChunk]:
    srv, _sess, wire_spec = _build_turn_mcp_context(envelope, ctx)
    reconciler = TerminalTextReconciler(enabled=should_reconcile_protocol(_driver_protocol(driver)))
    with ExitStack() as stack:
        if srv is not None:
            _ = stack.enter_context(srv)
        if wire_spec is not None:
            eff_spec = replace(wire_spec, mcp_url=srv.url) if srv is not None else wire_spec
            _ = stack.enter_context(TurnWireSessionScope.bind(eff_spec))
        custom = _call_driver_stream(driver, handle, envelope, ctx)
        if custom:
            yield from _reconciled_chunks(reconciler, custom)
            return
        raw_ctx = ctx.get("extra_turn_context")
        turn_ctx = cast(dict[str, Any], raw_ctx) if isinstance(raw_ctx, dict) else (dict(cast(Mapping[str, Any], raw_ctx)) if raw_ctx else {})
        timeouts = cast(tuple[float, float], ctx.get("timeouts", (30.0, 120.0)))
        dl_or_idle: float | _TurnDeadlines = ctx["deadlines"] if isinstance(ctx.get("deadlines"), _TurnDeadlines) else timeouts[1]
        _send_turn_input(driver, handle, str(ctx["prompt"]), turn_ctx, timeouts[0])
        on_dispatched()
        if srv is not None:
            yield from _reconciled_chunks(reconciler, _stream_with_mcp(driver, handle, turn_ctx, dl_or_idle, srv))
        else:
            yield from _reconciled_chunks(reconciler, _stream_plain(driver, handle, turn_ctx, dl_or_idle))


def cancel_driver_turn(driver: Any, handle: Any, turn_context: Mapping[str, object] | None) -> None:
    payload = _resolve_cancel_payload(driver, turn_context if turn_context else {})
    if payload:
        try:
            handle.write(payload)
        except Exception as exc:
            logger.warning("resident_cancel_write_failed: %s", type(exc).__name__)

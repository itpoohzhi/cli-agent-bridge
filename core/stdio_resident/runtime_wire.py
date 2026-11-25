"""Wire-protocol execution bridge between ResidentBridgeRuntime and StdioProtocolDriver."""

from __future__ import annotations

import inspect
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import suppress
from typing import Any, cast

from core.resident_canonical import _fail_if
from core.stdio_resident.process_io import TIMEOUT
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.runtime_types import PreDispatchResidentError, ResidentStreamError
from core.stdio_resident.session_manager import _build_cancel_payload, _track_fsm_ids


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


def prepare_runtime_spec(
    driver: Any,
    envelope: Any,
    base_argv: list[str],
    iso: Any,
) -> tuple[list[str], str, dict[str, str] | None]:
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


def _read_decoded_step(driver: Any, handle: Any, idle_s: float, turn_ctx: dict[str, Any]) -> tuple[DecodedChunk | None, bool, bool]:
    kind, tagged = _read_next(handle, idle_s)
    _fail_if(kind == TIMEOUT, ResidentStreamError("resident_turn_timeout", code="turn_timeout"))
    _fail_if(isinstance(tagged, type(None)), ResidentStreamError("resident process ended before the terminal marker", code="upstream_incomplete_stream"))
    return _decode_tagged_line(driver, handle, tagged, turn_ctx)


def stream_driver_turn(
    driver: Any,
    handle: Any,
    envelope: Any,
    ctx: dict[str, Any],
    on_dispatched: Callable[[], None],
) -> Iterator[DecodedChunk]:
    custom = _call_driver_stream(driver, handle, envelope, ctx)
    if custom:
        yield from custom
    else:
        raw_ctx = ctx.get("extra_turn_context")
        turn_ctx = raw_ctx if isinstance(raw_ctx, dict) else (dict(raw_ctx) if raw_ctx else {})
        timeouts = cast(tuple[float, float], ctx["timeouts"])
        _send_turn_input(driver, handle, str(ctx["prompt"]), turn_ctx, timeouts[0])
        on_dispatched()
        done = False
        while not done:
            chunk, done, emit = _read_decoded_step(driver, handle, timeouts[1], turn_ctx)
            if emit:
                yield cast(DecodedChunk, chunk)


def cancel_driver_turn(driver: Any, handle: Any, turn_context: Mapping[str, object] | None) -> None:
    payload = _build_cancel_payload(driver, turn_context if turn_context else {})
    if payload:
        with suppress(Exception):
            handle.write(payload)

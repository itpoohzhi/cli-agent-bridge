#!/usr/bin/env python3
"""Детерминированный резидентный процесс для проверки stdio-протоколов."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from types import FrameType
from typing import Literal, cast

Protocol = Literal["stream-json", "stream-jsonrpc", "acp"]
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


@dataclass(frozen=True)
class Args:
    protocol: Protocol
    delay: float
    init_banner: bool


def _parse_args() -> Args:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--protocol",
        choices=("stream-json", "stream-jsonrpc", "acp"),
        default="stream-json",
    )
    _ = parser.add_argument("--delay", type=float, default=0.0)
    _ = parser.add_argument("--init-banner", action="store_true")
    namespace = parser.parse_args()
    return Args(
        protocol=cast(Protocol, namespace.protocol),
        delay=cast(float, namespace.delay),
        init_banner=cast(bool, namespace.init_banner),
    )


def _graceful_exit(_signum: int, _frame: FrameType | None) -> None:
    raise SystemExit(0)


def _emit(payload: JsonObject) -> None:
    _ = sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _ = sys.stdout.flush()


def _pause(delay: float) -> None:
    if delay > 0.0:
        time.sleep(delay)


def _parse_turn(line: str) -> JsonObject:
    if line == "turn":
        return {"prompt": "turn"}
    try:
        payload = _to_json_value(cast(object, json.loads(line)))
    except json.JSONDecodeError:
        return {"prompt": line}
    if isinstance(payload, dict):
        return payload
    return {"prompt": payload}


def _to_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_to_json_value(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        result: JsonObject = {}
        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            result[key] = _to_json_value(item)
        return result
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _prompt_text(payload: JsonObject) -> str:
    prompt = payload.get("prompt")
    if prompt is None:
        params = payload.get("params")
        if isinstance(params, dict):
            prompt = params.get("prompt")
    return str(prompt) if prompt is not None else "turn"


def _has_tool_call(payload: JsonObject) -> bool:
    if bool(payload.get("tool_call")):
        return True
    params = payload.get("params")
    return isinstance(params, dict) and bool(params.get("tool_call"))


def _emit_stream_json(payload: JsonObject, delay: float) -> None:
    prompt = _prompt_text(payload)
    for delta in ("echo: ", prompt):
        _emit({"type": "content", "delta": delta})
        _pause(delay)
    terminal = "tool_turn_stop" if _has_tool_call(payload) else "done"
    _emit({"type": terminal})


def _emit_stream_jsonrpc(payload: JsonObject, delay: float) -> None:
    prompt = _prompt_text(payload)
    for delta in ("echo: ", prompt):
        _emit(
            {
                "jsonrpc": "2.0",
                "method": "progress",
                "params": {"delta": delta},
            }
        )
        _pause(delay)
    _emit(
        {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "result": {"status": "ok"},
        }
    )


def _emit_acp(payload: JsonObject, delay: float) -> None:
    prompt = _prompt_text(payload)
    for chunk in ("echo: ", prompt):
        _emit({"event": "stream", "payload": chunk})
        _pause(delay)
    _emit({"event": "turn_complete"})


def _handle_directive(line: str) -> bool:
    if line == "__CRASH__":
        raise SystemExit(1)
    if line == "__HANG__":
        while True:
            time.sleep(3600)
    if line == "__CLOSE_STDOUT__":
        _ = sys.stdout.close()
        return True
    return False


def _run(protocol: Protocol, delay: float, init_banner: bool) -> int:
    if init_banner:
        _emit({"type": "init", "status": "ready"})

    emitters: dict[Protocol, Callable[[JsonObject, float], None]] = {
        "stream-json": _emit_stream_json,
        "stream-jsonrpc": _emit_stream_jsonrpc,
        "acp": _emit_acp,
    }
    emitter = emitters[protocol]
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        if _handle_directive(line):
            continue
        emitter(_parse_turn(line), delay)
    return 0


def main() -> int:
    args = _parse_args()
    _ = signal.signal(signal.SIGINT, _graceful_exit)
    _ = signal.signal(signal.SIGTERM, _graceful_exit)
    try:
        return _run(args.protocol, args.delay, args.init_banner)
    except (BrokenPipeError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

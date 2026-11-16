"""Административный POST карантина без обратной зависимости от server."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

from core.http_post_context import PostHandler
from core.model_penalty import ModelPenaltyTracker

_MAX_BODY_BYTES = 64 * 1024
_DEFAULT_DURATION_S = 300.0


def _framing_error(handler: PostHandler, status: int, message: str) -> None:
    handler.close_connection = True
    handler._reject(status, "invalid_request", message)


def _read_body(handler: PostHandler) -> bytes | None:
    if handler.headers.get("Transfer-Encoding") is not None:
        return _framing_error(handler, 400, "Transfer-Encoding is not supported")
    lengths = handler.headers.get_all("Content-Length", [])
    if len(lengths) != 1:
        return _framing_error(handler, 400, "A single Content-Length is required")
    raw_length = lengths[0].strip()
    if not raw_length.isascii() or not raw_length.isdecimal():
        return _framing_error(handler, 400, "Invalid Content-Length")
    try:
        length = int(raw_length)
    except ValueError:
        return _framing_error(handler, 400, "Invalid Content-Length")
    if length > _MAX_BODY_BYTES:
        return _framing_error(handler, 413, "Request body is too large")
    raw_body = handler.rfile.read(length)
    if len(raw_body) != length:
        return _framing_error(handler, 400, "Incomplete request body")
    return raw_body


def _set_enabled(
    handler: PostHandler, body: dict[str, Any], tracker: ModelPenaltyTracker,
) -> None:
    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        return handler._reject(400, "invalid_request", "enabled must be a boolean")
    result = tracker.set_enabled(enabled)
    handler._send(200, {
        "ok": True, "action": "set_enabled", "enabled": result,
        "max_start_fails": tracker.max_start_fails,
    })


def _ban(
    handler: PostHandler, body: dict[str, Any], model: str, tracker: ModelPenaltyTracker,
) -> None:
    raw_duration = body.get("duration_s", _DEFAULT_DURATION_S)
    try:
        if isinstance(raw_duration, bool):
            raise ValueError("boolean duration")
        duration_s = float(raw_duration)
        if not math.isfinite(duration_s) or duration_s < 0:
            raise ValueError("invalid duration")
    except (TypeError, ValueError, OverflowError):
        handler._reject(400, "invalid_request", "duration_s must be finite and nonnegative")
        return
    try:
        status = tracker.manually_penalize(model, duration_s)
    except ValueError as exc:
        handler._reject(400, "invalid_request", str(exc))
        return
    handler._send(200, {"ok": True, "action": "ban", "model": model, "status": status})


def _model_action(
    handler: PostHandler, body: dict[str, Any], tracker: ModelPenaltyTracker,
) -> None:
    model = body.get("model")
    if not isinstance(model, str) or not model.strip() or model.strip().lower() == "_meta":
        handler._reject(
            400, "invalid_request", "model must be a nonempty string other than '_meta'",
        )
        return
    if body.get("action") == "unban":
        tracker.unpenalize_model(model)
        handler._send(200, {"ok": True, "action": "unban", "model": model})
        return
    _ban(handler, body, model, tracker)


def _dispatch(
    handler: PostHandler, body: dict[str, Any], tracker: ModelPenaltyTracker,
) -> None:
    action = body.get("action")
    if action == "set_enabled":
        return _set_enabled(handler, body, tracker)
    if action in ("unban", "ban"):
        return _model_action(handler, body, tracker)
    if action == "clear_all":
        tracker.reset_all()
        handler._send(200, {"ok": True, "action": "clear_all"})
        return
    handler._send(400, {
        "error": {"message": f"unknown action: {action}", "type": "invalid_request"},
    })


def handle_quarantine_post(
    handler: PostHandler, auth_ok: Callable[[PostHandler], bool],
    tracker: ModelPenaltyTracker, backends: object,
) -> None:
    """Проверяет авторизацию до чтения тела и исполняет прежний контракт POST."""
    if not auth_ok(handler):
        handler._send(401, {
            "error": {"message": "unauthorized", "type": "auth_error", "code": 401},
        })
        return
    raw_body = _read_body(handler)
    if raw_body is None:
        return
    try:
        body = json.loads(raw_body)
    except (ValueError, UnicodeError, RecursionError):
        return handler._reject(400, "invalid_request", "Invalid JSON body")
    if not isinstance(body, dict):
        return handler._reject(400, "invalid_request", "JSON body must be an object")
    _dispatch(handler, body, tracker)

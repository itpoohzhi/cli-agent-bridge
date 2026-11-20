"""SSE error-фрейм и HTTP-статус для сбоя резидентного хода (в т.ч. до первого чанка)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

DONE_FRAME: Final[str] = "data: [DONE]\n\n"
_RATE_LIMIT_MARKERS: Final[tuple[str, ...]] = ("429", "rate limit", "rate_limit", "quota")


@dataclass(frozen=True, slots=True)
class TurnErrorResponse:
    """Готовый ответ: статус (200, если заголовки уже ушли), SSE-фрейм и JSON-тело."""

    status: int
    error_type: str
    code: str
    message: str
    sse: str
    body: dict[str, object]


def classify_turn_error(error: BaseException) -> tuple[int, str, str]:
    """Возвращает `(status, error_type, code)` по семантике сбоя, не по имени агента."""
    if isinstance(error, TimeoutError):
        return 504, "timeout_error", "turn_timeout"
    text = str(error).lower()
    if any(marker in text for marker in _RATE_LIMIT_MARKERS):
        return 429, "rate_limit_error", "rate_limit_exceeded"
    return 502, "upstream_error", "resident_turn_failed"


def build_turn_error(
    error: BaseException,
    live_sent: int = 0,
    *,
    max_chars: int = 500,
) -> TurnErrorResponse:
    """Формирует error-фрейм + `data: [DONE]`; статус ошибки — только при `live_sent == 0`.

    Если клиенту уже отдан хотя бы один байт (`live_sent > 0`), статус остаётся 200,
    а ошибка доставляется внутри потока.
    """
    status, error_type, code = classify_turn_error(error)
    message = (str(error) or error.__class__.__name__)[: max(1, max_chars)]
    body: dict[str, object] = {"error": {"message": message, "type": error_type, "code": code}}
    frame = "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"
    return TurnErrorResponse(
        status=status if not live_sent else 200,
        error_type=error_type, code=code, message=message,
        sse=frame + DONE_FRAME, body=body,
    )

"""Request-scoped сбор и публикация квитанций потерь agy-bridge (AD-006/007)."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol, cast

from core.turn_usage_fsm import should_emit_wire_usage

from .input_guard_policy import ClientCompactionRequired
from .loss_contract_config import read_loss_contract_settings
from .loss_receipt import LossReceipt, merge_conservative

__all__ = (
    "LossReceiptCollector",
    "begin_request_scope",
    "record_build",
    "record_lossless",
    "send_client_compaction_required",
    "usage_chunk_due",
    "usage_payload",
)

_LOGGER = logging.getLogger(__name__)
_CURRENT: ContextVar[LossReceiptCollector | None] = ContextVar(
    "agy_loss_receipt_collector", default=None
)


class LossReceiptCollector:
    """Владелец квитанций одного HTTP-запроса; разделяемого состояния нет."""

    __slots__: tuple[str, ...] = ("_receipts",)

    def __init__(self) -> None:
        self._receipts: list[LossReceipt] = []

    def record_build(self, receipt: LossReceipt) -> None:
        """Добавить квитанцию одной фактической сборки промпта."""
        self._receipts.append(receipt)

    def record_lossless(self) -> None:
        """Зафиксировать сборку без потерь, если детальные счётчики не нужны."""
        self.record_build(LossReceipt())

    def merged(self) -> LossReceipt | None:
        """Вернуть консервативный снимок худшей квитанции запроса."""
        return merge_conservative(tuple(self._receipts))


@contextmanager
def begin_request_scope() -> Generator[LossReceiptCollector]:
    """Установить новый collector и гарантированно восстановить родительский."""
    collector = LossReceiptCollector()
    token = _CURRENT.set(collector)
    try:
        yield collector
    finally:
        _CURRENT.reset(token)


def record_build(receipt: LossReceipt) -> None:
    """Записать сборку в текущий scope; orphan не создаёт скрытое состояние."""
    collector = _CURRENT.get()
    if collector is None:
        _LOGGER.warning("loss_receipt_orphan")
        return
    collector.record_build(receipt)


def record_lossless() -> None:
    """Записать ранний lossless-return в текущий request scope."""
    record_build(LossReceipt())


def _legacy_usage_payload(
    usage: dict[str, object], resolved: object = None
) -> dict[str, object]:
    """Прежнее преобразование usage без каких-либо добавлений квитанции."""
    if not should_emit_wire_usage(resolved):
        return {}
    if isinstance(resolved, dict):
        wire = cast("dict[str, object]", resolved).get("wire")
        if isinstance(wire, dict):
            return dict(cast("dict[str, object]", wire))
    output = cast("int", usage.get("output_tokens", 0))
    thinking = cast("int", usage.get("thinking_tokens", 0))
    return {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": output + thinking,
        "total_tokens": usage.get("total_tokens", 0),
    }


def _enabled() -> bool:
    return read_loss_contract_settings().loss_receipt_enabled


def usage_payload(
    usage: dict[str, object], resolved: object = None
) -> dict[str, object]:
    """Сформировать legacy usage и при активном флаге приложить receipt.

    Подавлённый пустой wire становится нулевым носителем только для
    ``truncated=true``. Lossless + suppressed usage остаётся пустым.
    """
    wire = _legacy_usage_payload(usage, resolved)
    collector = _CURRENT.get() if _enabled() else None
    receipt = collector.merged() if collector is not None else None
    if receipt is None or (not wire and not receipt.truncated):
        return wire
    if not wire:
        wire = cast(
            "dict[str, object]",
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
    wire["x_bridge_loss"] = receipt.to_wire()
    return wire


def usage_chunk_due(usage: dict[str, object], resolved: object = None) -> bool:
    """Нужен финальный SSE usage chunk: положительный usage или loss carrier."""
    receipt = usage.get("x_bridge_loss")
    if isinstance(receipt, dict):
        loss = cast("dict[str, object]", receipt)
        if loss.get("truncated") is True:
            return True
    return should_emit_wire_usage(resolved) and any(
        (usage.get("prompt_tokens"), usage.get("completion_tokens"))
    )


class _SendHandler(Protocol):
    def _send(self, code: int, payload: dict[str, object]) -> None: ...


def send_client_compaction_required(
    handler: _SendHandler, error: ClientCompactionRequired
) -> None:
    """Отправить заранее построенное тело UNFIT как HTTP 400."""
    # Адаптер вызывается из Handler и использует его существующий приватный фасад.
    handler._send(400, error.body)  # pyright: ignore[reportPrivateUsage]

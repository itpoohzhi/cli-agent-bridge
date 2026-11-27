"""Чистая политика входного гарда agy-bridge (AD-010/AD-011, BND-001).

Без I/O, env и часов. Окно = якорь + финальная атомарная группа + новейшие
группы (атомарно по группам); блоки вне окна — dropped; якорь+актив не
помещаются целиком — UNFIT: ``ClientCompactionRequired`` и HTTP 400
``build_rejection_body``. Группировка — как в history_compaction_domain.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .history_compaction_domain import (
    DEFAULT_INPUT_GUARD_BYTES,
    PromptBlock,
    json_text_bytes,
)
from .history_user_classifier import is_synthetic_user_block as _synthetic
from .loss_receipt import LossReceipt


class InputGuardMode(StrEnum):
    """Режим входного гарда (AD-011); дефолт — compact_or_reject."""

    LEGACY = "legacy"
    COMPACT_OR_REJECT = "compact_or_reject"


class GuardVerdict(StrEnum):
    """Вердикт гарда: legacy-путь, вход помещается, окно, UNFIT-отказ."""

    LEGACY = "legacy"
    FIT = "fit"
    WINDOW = "window"
    UNFIT = "unfit"


def _validate_ints(*pairs: tuple[str, int]) -> None:
    for name, value in pairs:
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class GuardDecision:
    """Иммутабельный итог гарда: вердикт, окно и счётчик dropped-блоков."""

    verdict: GuardVerdict
    window: tuple[PromptBlock, ...]
    dropped_messages: int
    input_bytes: int
    guard_bytes: int

    def __post_init__(self) -> None:
        if type(self.verdict) is not GuardVerdict:
            raise ValueError("verdict must be GuardVerdict")
        for name in ("dropped_messages", "input_bytes", "guard_bytes"):
            _validate_ints((name, getattr(self, name)))


def _group_blocks(blocks: Sequence[PromptBlock]) -> tuple[tuple[PromptBlock, ...], ...]:
    """Группы как в history_compaction_domain: assistant+tool calls/results."""
    groups: list[tuple[PromptBlock, ...]] = []
    pos = 0
    while pos < len(blocks):
        block = blocks[pos]
        if block.role == "assistant" and "[tool call " in block.rendered:
            end = pos + 1
            while end < len(blocks) and blocks[end].role == "tool":
                end += 1
            groups.append(tuple(blocks[pos:end]))
            pos = end
        else:
            groups.append((block,))
            pos += 1
    return tuple(groups)


def _anchor_group_count(groups: Sequence[tuple[PromptBlock, ...]]) -> int:
    """Якорь до первого реального user; иначе до любого user; иначе system*."""
    for idx, group in enumerate(groups):
        if any(b.role == "user" and not _synthetic(b.rendered) for b in group):
            return idx + 1
    leading = 0
    in_leading = True
    for idx, group in enumerate(groups):
        roles = [b.role for b in group]
        if "user" in roles:
            return idx + 1
        if in_leading and roles == ["system"]:
            leading += 1
        else:
            in_leading = False
    return leading


def _mandatory_indices(groups: Sequence[tuple[PromptBlock, ...]]) -> frozenset[int]:
    """Якорь плюс только финальная атомарная группа хвоста: старые tool-группы
    хода без нового user добирает _newest_fit (Hermes: 845 msg -> WINDOW)."""
    mandatory = set(range(_anchor_group_count(groups)))
    if groups:
        mandatory.add(len(groups) - 1)
    return frozenset(mandatory)


def _text_bytes(blocks: Sequence[PromptBlock], separator: str) -> int:
    return json_text_bytes(separator.join(b.rendered for b in blocks))


def _newest_fit(
    groups: Sequence[tuple[PromptBlock, ...]],
    mandatory: frozenset[int],
    used: int,
    guard_bytes: int,
    separator: str,
) -> frozenset[int]:
    """Новейшие группы целиком, пока влезают; первая не влезшая — стоп."""
    sep_bytes = json_text_bytes(separator)
    extra: set[int] = set()
    for idx in range(len(groups) - 1, -1, -1):
        if idx in mandatory:
            continue
        cost = _text_bytes(groups[idx], separator) + sep_bytes
        if used + cost > guard_bytes:
            break
        extra.add(idx)
        used += cost
    return frozenset(extra)


def select_bounded_window(
    blocks: Sequence[PromptBlock],
    mode: InputGuardMode | str = InputGuardMode.COMPACT_OR_REJECT,
    guard_bytes: int = DEFAULT_INPUT_GUARD_BYTES,
    separator: str = "\n\n",
) -> GuardDecision:
    """Окно под гард (AD-011): LEGACY — вход без изменений, FIT — вход
    помещается, WINDOW — окно+dropped, UNFIT — якорь+актив не помещаются."""
    resolved = InputGuardMode(mode)
    _validate_ints(("guard_bytes", guard_bytes))
    if type(separator) is not str:
        raise ValueError("separator must be str")
    ordered = tuple(blocks)
    input_bytes = _text_bytes(ordered, separator)
    if resolved is InputGuardMode.LEGACY:
        return GuardDecision(GuardVerdict.LEGACY, ordered, 0, input_bytes, guard_bytes)
    if input_bytes <= guard_bytes:
        return GuardDecision(GuardVerdict.FIT, ordered, 0, input_bytes, guard_bytes)
    groups = _group_blocks(ordered)
    mandatory = _mandatory_indices(groups)
    kept = tuple(b for i in sorted(mandatory) for b in groups[i])
    used = _text_bytes(kept, separator)
    if used > guard_bytes:
        return GuardDecision(
            GuardVerdict.UNFIT, (), len(ordered), input_bytes, guard_bytes
        )
    selected = mandatory | _newest_fit(groups, mandatory, used, guard_bytes, separator)
    window = tuple(b for i in sorted(selected) for b in groups[i])
    dropped = len(ordered) - len(window)
    return GuardDecision(GuardVerdict.WINDOW, window, dropped, input_bytes, guard_bytes)


_REJECTION_MESSAGE = (
    "client_compaction_required (context length exceeded): history of "
    "{history_bytes} bytes exceeds agy-bridge input_guard {guard_bytes} bytes and the active tool group "
    "cannot be kept intact within the configured prompt cap {cap_bytes} bytes; "
    "compact the conversation and retry"
)


def build_rejection_body(
    history_bytes: int, guard_bytes: int, cap_bytes: int, original_messages: int
) -> dict[str, object]:
    """Тело HTTP 400 (AD-010): только целые числа в message и квитанции."""
    names = ("history_bytes", "guard_bytes", "cap_bytes", "original_messages")
    values = (history_bytes, guard_bytes, cap_bytes, original_messages)
    _validate_ints(*zip(names, values))
    receipt = LossReceipt(
        truncated=True,
        original_messages=original_messages,
        original_prompt_bytes=history_bytes,
        dropped_messages=original_messages,
        fallback_reason="input_guard",
        configured_prompt_cap_bytes=cap_bytes,
    )
    return {
        "error": {
            "type": "invalid_request_error",
            "code": "context_length_exceeded",
            "param": "messages",
            "x_reason": "client_compaction_required",
            "message": _REJECTION_MESSAGE.format(
                history_bytes=history_bytes,
                guard_bytes=guard_bytes,
                cap_bytes=cap_bytes,
            ),
            "x_bridge_loss": receipt.to_wire(),
        }
    }


class ClientCompactionRequired(Exception):
    """UNFIT: клиент обязан компактить историю; ``body`` готов для do_POST."""

    def __init__(
        self,
        history_bytes: int,
        guard_bytes: int,
        cap_bytes: int,
        original_messages: int,
    ) -> None:
        self.body: dict[str, object] = build_rejection_body(
            history_bytes, guard_bytes, cap_bytes, original_messages
        )
        super().__init__("client_compaction_required")

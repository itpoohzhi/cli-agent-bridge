"""Чистый домен квитанции потерь промпта agy-bridge (AD-005/AD-006).

Счётчики относятся только к непустым отрендеренным блокам, предложенным
prompt builder. Каждый блок попадает ровно в один класс: kept (verbatim),
partial (сохранилась голова), digested (исходный index в digested_positions)
или dropped. Модуль не читает env, часы и не выполняет I/O.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from .history_compaction_domain import DEFAULT_MIDDLE_PRUNED_MARKER, PromptBlock

LOSS_RECEIPT_SCHEMA_VERSION = "loss-receipt/v1"

__all__ = (
    "LOSS_RECEIPT_SCHEMA_VERSION",
    "BlockClassification",
    "LossReceipt",
    "RawBlock",
    "classify_blocks",
    "merge_conservative",
    "to_wire",
)

RawBlock: TypeAlias = PromptBlock | tuple[int, str, str] | tuple[str, str]
WireValue: TypeAlias = str | int | bool
_COUNT_FIELDS = (
    "original_messages",
    "effective_messages",
    "original_prompt_bytes",
    "effective_prompt_bytes",
    "dropped_messages",
    "digested_messages",
    "truncated_active_tools",
    "configured_prompt_cap_bytes",
    "partial_messages",
)
_CLASSIFICATION_FIELDS = (
    "kept_messages",
    "partial_messages",
    "digested_messages",
    "dropped_messages",
)


def _validate_non_negative_ints(instance: object, names: Iterable[str]) -> None:
    for name in names:
        value = getattr(instance, name)
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class BlockClassification:
    """Взаимоисключающие счётчики исходных блоков одной сборки промпта."""

    kept_messages: int = 0
    partial_messages: int = 0
    digested_messages: int = 0
    dropped_messages: int = 0

    def __post_init__(self) -> None:
        _validate_non_negative_ints(self, _CLASSIFICATION_FIELDS)

    @property
    def original_messages(self) -> int:
        """Число непустых исходных блоков по закону сохранения."""
        return (
            self.kept_messages
            + self.partial_messages
            + self.digested_messages
            + self.dropped_messages
        )

    @property
    def effective_messages(self) -> int:
        """Блоки, чьё содержимое полностью или частично дошло до модели."""
        return self.kept_messages + self.partial_messages


@dataclass(frozen=True, slots=True)
class LossReceipt:
    """Иммутабельная квитанция ``loss-receipt/v1`` для ``usage.x_bridge_loss``."""

    schema_version: str = LOSS_RECEIPT_SCHEMA_VERSION
    truncated: bool = False
    original_messages: int = 0
    effective_messages: int = 0
    original_prompt_bytes: int = 0
    effective_prompt_bytes: int = 0
    dropped_messages: int = 0
    digested_messages: int = 0
    truncated_active_tools: int = 0
    fallback_reason: str = ""
    configured_prompt_cap_bytes: int = 0
    partial_messages: int = 0
    compaction_mode: str = ""
    prompt_mode: str = ""
    history_budget_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.schema_version != LOSS_RECEIPT_SCHEMA_VERSION:
            raise ValueError("schema_version must be loss-receipt/v1")
        if type(self.truncated) is not bool:
            raise ValueError("truncated must be bool")
        _validate_non_negative_ints(self, _COUNT_FIELDS)
        for name in ("fallback_reason", "compaction_mode", "prompt_mode"):
            if type(getattr(self, name)) is not str:
                raise ValueError(f"{name} must be str")
        if self.history_budget_bytes is not None:
            _validate_non_negative_ints(self, ("history_budget_bytes",))
        accounted = self.effective_messages + self.digested_messages
        accounted += self.dropped_messages
        if accounted != self.original_messages:
            raise ValueError("message conservation violated")
        if self.partial_messages > self.effective_messages:
            raise ValueError("partial_messages must not exceed effective_messages")
        loss = self.partial_messages + self.digested_messages + self.dropped_messages
        if not self.truncated and (
            loss or self.truncated_active_tools or self.fallback_reason
        ):
            raise ValueError("loss indicators require truncated=true")

    @property
    def kept_messages(self) -> int:
        """Число verbatim-блоков; производное поле не сериализуется."""
        return self.effective_messages - self.partial_messages

    def to_wire(self) -> dict[str, WireValue]:
        """Сериализовать только явно разрешённые поля v1, без None."""
        wire: dict[str, WireValue] = {
            "schema_version": self.schema_version,
            "truncated": self.truncated,
            "original_messages": self.original_messages,
            "effective_messages": self.effective_messages,
            "original_prompt_bytes": self.original_prompt_bytes,
            "effective_prompt_bytes": self.effective_prompt_bytes,
            "dropped_messages": self.dropped_messages,
            "digested_messages": self.digested_messages,
            "truncated_active_tools": self.truncated_active_tools,
            "fallback_reason": self.fallback_reason,
            "configured_prompt_cap_bytes": self.configured_prompt_cap_bytes,
        }
        if self.partial_messages:
            wire["partial_messages"] = self.partial_messages
        if self.compaction_mode:
            wire["compaction_mode"] = self.compaction_mode
        if self.prompt_mode:
            wire["prompt_mode"] = self.prompt_mode
        if self.history_budget_bytes is not None:
            wire["history_budget_bytes"] = self.history_budget_bytes
        return wire


def _block_index_text(block: RawBlock, position: int) -> tuple[int, str]:
    if isinstance(block, PromptBlock):
        return block.index, block.rendered
    if len(block) == 3:
        index, _, rendered = block
    else:
        _, rendered = block
        index = position
    return int(index), str(rendered)


def _take_occurrence(prompt: str, needle: str, remaining: dict[str, int]) -> bool:
    """Сопоставить повторяющийся блок не более числа его копий в prompt."""
    if not needle:
        return False
    count = remaining.get(needle)
    if count is None:
        count = prompt.count(needle)
    if count <= 0:
        return False
    remaining[needle] = count - 1
    return True


def _partial_head(rendered: str, prompt: str, marker: str) -> str:
    if "\n" in rendered:
        return rendered.partition("\n")[0]
    marker_pos = prompt.find(marker) if marker else -1
    while marker_pos >= 0:
        line_start = prompt.rfind("\n", 0, marker_pos) + 1
        head = prompt[line_start:marker_pos]
        if head and rendered.startswith(head):
            return head
        marker_pos = prompt.find(marker, marker_pos + len(marker))
    return ""


def classify_blocks(
    blocks: Sequence[RawBlock],
    prompt: str,
    digested_positions: Collection[int] = (),
    middle_pruned_marker: str = DEFAULT_MIDDLE_PRUNED_MARKER,
) -> BlockClassification:
    """Классифицировать исходные блоки по фактически собранному prompt.

    ``digested_positions`` содержит исходные ``PromptBlock.index`` (для
    двухэлементных tuple — позицию в ``blocks``). Digest имеет приоритет над
    текстовым совпадением. Повторяющиеся verbatim-блоки сопоставляются с
    учётом числа вхождений, поэтому одна сохранённая копия не маскирует drop.
    """
    digested = frozenset(digested_positions)
    verbatim_remaining: dict[str, int] = {}
    head_remaining: dict[str, int] = {}
    kept = partial = digested_count = dropped = 0
    for position, block in enumerate(blocks):
        index, rendered = _block_index_text(block, position)
        if not rendered:
            continue
        if index in digested:
            digested_count += 1
            continue
        head = _partial_head(rendered, prompt, middle_pruned_marker)
        if _take_occurrence(prompt, rendered, verbatim_remaining):
            kept += 1
            _take_occurrence(prompt, head, head_remaining)
        elif head and _take_occurrence(prompt, head, head_remaining):
            partial += 1
        else:
            dropped += 1
    return BlockClassification(kept, partial, digested_count, dropped)


def merge_conservative(receipts: Iterable[LossReceipt]) -> LossReceipt | None:
    """Выбрать худшую целую квитанцию: truncated, затем dropped+digested.

    Смешивание max-значений разных сборок нарушило бы conservation, поэтому
    возвращается один неизменный входной объект. Пустой набор означает,
    что квитанция не строилась.
    """
    return max(
        receipts,
        key=lambda item: (
            item.truncated,
            item.dropped_messages + item.digested_messages,
        ),
        default=None,
    )


def to_wire(receipt: LossReceipt) -> dict[str, WireValue]:
    """Функциональная форма ``LossReceipt.to_wire`` для адаптеров."""
    return receipt.to_wire()

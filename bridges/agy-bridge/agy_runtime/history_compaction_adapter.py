"""Адаптер подключения домена компакции истории к мосту agy (AD-004).

Единственная точка входа ``render_or_compact_blocks``: при выключенном
флаге дословно делегирует legacy-обрезке, при включённом — доменной
компакции с fallback на legacy при превышении входного гарда, ошибке или
выходе за лимит. Входной гард делегирован ``input_guard_policy`` (режим из
``loss_contract_config``): UNFIT активной группы -> ``ClientCompactionRequired``.
Каждая сборка записывает одну квитанцию потерь в ``loss_receipt_context``.
Все дефолты компакции заданы ровно один раз в домене (SSOT).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from agy_runtime.history_compaction_domain import (
    DEFAULT_INPUT_GUARD_BYTES,
    DEFAULT_MIDDLE_PRUNED_MARKER,
    CompactionConfig,
    PromptBlock,
    anchor_prefix_sha256,
    compact_prompt_blocks,
    json_text_bytes,
)
from agy_runtime.history_user_classifier import is_synthetic_user_block
from agy_runtime.input_guard_policy import (
    ClientCompactionRequired,
    GuardDecision,
    GuardVerdict,
    InputGuardMode,
    select_bounded_window,
)
from agy_runtime.loss_contract_config import LossContractSettings, read_loss_contract_settings
from agy_runtime.loss_receipt import BlockClassification, LossReceipt, classify_blocks
from agy_runtime.loss_receipt_context import record_build

RawBlock = PromptBlock | tuple[int, str, str] | tuple[str, str]
LegacyPrune = Callable[[Sequence[RawBlock], str, int], str]


@dataclass(frozen=True, slots=True)
class CompactionAdapterRequest:
    """Вход адаптера: блоки server-формата, лимит и legacy-делегат."""

    blocks: Sequence[RawBlock]
    tail_block: str
    limit_bytes: int
    enabled: bool
    legacy_prune: LegacyPrune
    log_fn: Callable[[str], None] | None = None
    config_path: Path | None = None  # источник dynamic_config для настроек
    size_fn: Callable[[str], int] | None = None
    middle_pruned_marker: str = DEFAULT_MIDDLE_PRUNED_MARKER
    separator: str = "\n\n"
    input_guard_bytes: int = DEFAULT_INPUT_GUARD_BYTES


@dataclass(frozen=True, slots=True)
class _Built:
    prompt: str
    mode: str
    reason: str = ""
    digested_positions: tuple[int, ...] = ()
    history_budget: int | None = None


@dataclass(frozen=True, slots=True)
class _LogRecord:
    mode: str
    prompt_bytes: int
    limit_bytes: int
    prompt_prefix_sha256: str
    digested: int
    dropped: int
    reason: str = ""


def _to_prompt_block(item: RawBlock, pos: int) -> PromptBlock:
    if isinstance(item, PromptBlock):
        return item
    index, role, rendered = item if len(item) == 3 else (pos, *item)
    return PromptBlock(index=int(index), role=str(role), rendered=str(rendered))


def _to_prompt_blocks(raw: Sequence[RawBlock]) -> tuple[PromptBlock, ...]:
    return tuple(_to_prompt_block(item, pos) for pos, item in enumerate(raw))


def _measure(request: CompactionAdapterRequest, text: str) -> int:
    return (request.size_fn or json_text_bytes)(text)


def _joined(blocks: Sequence[PromptBlock], request: CompactionAdapterRequest) -> str:
    parts = [block.rendered for block in blocks]
    if request.tail_block:
        parts.append(request.tail_block)
    return request.separator.join(parts).strip()


def _dropped_count(blocks: Sequence[PromptBlock], result: str) -> int:
    return sum(1 for block in blocks if block.rendered and block.rendered not in result)


def _emit(log_fn: Callable[[str], None] | None, r: _LogRecord) -> None:
    if log_fn:
        line = (
            f"history compaction: mode={r.mode} prompt_bytes={r.prompt_bytes} limit={r.limit_bytes} "
            f"prompt_prefix_sha256={r.prompt_prefix_sha256} digested={r.digested} dropped={r.dropped}"
        )
        log_fn(line + (f" reason={r.reason}" if r.reason else ""))


def _changed_or_overflow(
    request: CompactionAdapterRequest, blocks: Sequence[PromptBlock], result: str
) -> bool:
    full = _joined(blocks, request)
    return result != full or _measure(request, full) > request.limit_bytes


def _run_legacy(
    request: CompactionAdapterRequest,
    blocks: Sequence[PromptBlock],
    mode: str,
    reason: str,
) -> _Built:
    """Legacy-путь: результат делегата без изменений + структурированный лог."""
    result = request.legacy_prune(request.blocks, request.tail_block, request.limit_bytes)
    if mode == "fallback" or _changed_or_overflow(request, blocks, result):
        sha = anchor_prefix_sha256(blocks, request.separator)
        size, dropped = _measure(request, result), _dropped_count(blocks, result)
        _emit(request.log_fn, _LogRecord(mode, size, request.limit_bytes, sha, 0, dropped, reason))
    return _Built(result, mode, reason)


def _tail_cost(request: CompactionAdapterRequest) -> int:
    return json_text_bytes(request.separator + request.tail_block) if request.tail_block else 0


def _build_config(request: CompactionAdapterRequest, atomic: bool = False) -> CompactionConfig:
    """Доменный лимит из фактического limit_bytes минус обёртка и хвост.

    Остальные параметры не задаются: действуют дефолты ``CompactionConfig``
    из домена — единственный источник истины (SSOT, RW-002).
    """
    wrap = request.size_fn("") - json_text_bytes("") if request.size_fn else 0
    overhead = max(wrap, 0)
    effective = max(request.limit_bytes - overhead - _tail_cost(request), 0)
    marker, sep = request.middle_pruned_marker, request.separator
    return CompactionConfig(limit_bytes=effective, middle_pruned_marker=marker, separator=sep, atomic_groups=atomic)


def _input_bytes(blocks: Sequence[PromptBlock], request: CompactionAdapterRequest) -> int:
    total = sum(json_text_bytes(block.rendered) for block in blocks)
    return total + (json_text_bytes(request.tail_block) if request.tail_block else 0)


def _over_limit(request: CompactionAdapterRequest, prompt: str) -> bool:
    return max(json_text_bytes(prompt), _measure(request, prompt)) > request.limit_bytes


def _reject(
    request: CompactionAdapterRequest, blocks: Sequence[PromptBlock]
) -> ClientCompactionRequired:
    """UNFIT: активная группа не помещается; тело 400 строит доменная политика."""
    original = sum(1 for block in blocks if block.rendered)
    history = _input_bytes(blocks, request)
    return ClientCompactionRequired(history, request.input_guard_bytes, request.limit_bytes, original)


def _window_request(
    request: CompactionAdapterRequest, decision: GuardDecision
) -> CompactionAdapterRequest:
    """Запрос для legacy-fallback: только блоки окна, прошедшего гард."""
    raw = tuple((b.index, b.role, b.rendered) for b in decision.window)
    return replace(request, blocks=raw) if decision.verdict is GuardVerdict.WINDOW else request


def _compact_window(
    request: CompactionAdapterRequest,
    settings: LossContractSettings,
    blocks: tuple[PromptBlock, ...],
    decision: GuardDecision,
) -> _Built:
    """Компакция окна гарда; UNFIT -> отказ, ошибка/переполнение -> legacy."""
    fallback = _window_request(request, decision)
    config = _build_config(request, settings.atomic_active_tools_enabled)
    try:
        result = compact_prompt_blocks(decision.window, config)
    except Exception:
        return _run_legacy(fallback, blocks, "fallback", "compact_error")
    prompt = request.separator.join(p for p in (result.prompt, request.tail_block) if p)
    unfit = not result.prompt and any(b.rendered for b in decision.window)
    if unfit and settings.input_guard_mode is InputGuardMode.COMPACT_OR_REJECT:
        raise _reject(request, blocks)
    if unfit or _over_limit(request, prompt):
        return _run_legacy(fallback, blocks, "fallback", "over_limit")
    dropped = result.dropped_count + decision.dropped_messages
    record = _LogRecord("compact", _measure(request, prompt), request.limit_bytes, result.prompt_prefix_sha256, result.digested_count, dropped)
    _emit(request.log_fn, record)
    return _Built(prompt, "compact", "", result.digested_positions, config.limit_bytes)


def _compact_or_fallback(
    request: CompactionAdapterRequest, settings: LossContractSettings
) -> _Built:
    """Компакция при включённом флаге; гард/ошибка/переполнение — по режиму."""
    try:
        blocks = _to_prompt_blocks(request.blocks)
    except Exception:
        return _run_legacy(request, (), "fallback", "compact_error")
    mode = settings.input_guard_mode
    over = _input_bytes(blocks, request) > request.input_guard_bytes
    if mode is InputGuardMode.LEGACY and over:
        return _run_legacy(request, blocks, "fallback", "input_guard")
    guard = max(request.input_guard_bytes - _tail_cost(request), 0)
    decision = select_bounded_window(blocks, mode, guard, request.separator)
    if decision.verdict is GuardVerdict.UNFIT:
        raise _reject(request, blocks)
    return _compact_window(request, settings, blocks, decision)


def _legacy_entry(request: CompactionAdapterRequest, _settings: LossContractSettings) -> _Built:
    return _run_legacy(request, _to_prompt_blocks(request.blocks), "legacy", "")


def _classify(
    request: CompactionAdapterRequest, blocks: Sequence[PromptBlock], built: _Built
) -> BlockClassification:
    marker = request.middle_pruned_marker
    return classify_blocks(blocks, built.prompt, built.digested_positions, marker)


def _lost(cls: BlockClassification) -> int:
    return cls.partial_messages + cls.digested_messages + cls.dropped_messages


def _active_tool_loss(
    blocks: Sequence[PromptBlock], request: CompactionAdapterRequest, built: _Built
) -> int:
    """Потерянные tool-блоки активной группы (после последнего реального user)."""
    real = [i for i, b in enumerate(blocks) if b.role == "user" and not is_synthetic_user_block(b.rendered)]
    tools = [b for b in blocks[(real[-1] + 1 if real else 0) :] if b.role == "tool"]
    return _lost(_classify(request, tools, built))


def _receipt(
    request: CompactionAdapterRequest, blocks: Sequence[PromptBlock], built: _Built
) -> LossReceipt:
    """Квитанция сборки: каждый непустой блок — kept/partial/digested/dropped."""
    cls = _classify(request, blocks, built)
    lost = _lost(cls)
    return LossReceipt(
        truncated=lost > 0,
        original_messages=cls.original_messages, effective_messages=cls.effective_messages,
        original_prompt_bytes=_measure(request, _joined(blocks, request)),
        effective_prompt_bytes=_measure(request, built.prompt),
        dropped_messages=cls.dropped_messages, digested_messages=cls.digested_messages,
        truncated_active_tools=_active_tool_loss(blocks, request, built) if lost else 0,
        fallback_reason=built.reason if lost else "",
        configured_prompt_cap_bytes=request.limit_bytes, partial_messages=cls.partial_messages,
        compaction_mode=built.mode, history_budget_bytes=built.history_budget,
    )


def _record(
    request: CompactionAdapterRequest, settings: LossContractSettings, built: _Built
) -> None:
    if not settings.loss_receipt_enabled:
        return
    try:
        blocks = _to_prompt_blocks(request.blocks)
    except Exception:
        blocks = ()
    record_build(_receipt(request, blocks, built))


def render_or_compact_blocks(request: CompactionAdapterRequest) -> str:
    """Единая точка входа: legacy при ``enabled=False``, иначе компакция."""
    settings = read_loss_contract_settings(config_path=request.config_path)
    entry = _compact_or_fallback if request.enabled else _legacy_entry
    built = entry(request, settings)
    _record(request, settings, built)
    return built.prompt

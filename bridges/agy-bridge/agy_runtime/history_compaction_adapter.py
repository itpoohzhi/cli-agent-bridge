"""Адаптер подключения домена компакции истории к мосту agy (AD-004).

Единственная точка входа ``render_or_compact_blocks``: при выключенном
флаге дословно делегирует legacy-обрезке, при включённом — доменной
компакции с fallback на legacy при превышении входного гарда, ошибке или
выходе за лимит. Параметры читаются через ``long_session_config``
(env > dynamic_config.json > дефолт), без хардкода капов сверх дефолтов.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from agy_runtime.history_compaction_domain import (
    DEFAULT_MIDDLE_PRUNED_MARKER,
    CompactionConfig,
    CompactionResult,
    PromptBlock,
    anchor_prefix_sha256,
    compact_prompt_blocks,
    json_text_bytes,
)
from agy_runtime.long_session_config import read_float_setting, read_int_setting

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
    config_path: Path | None = None
    size_fn: Callable[[str], int] | None = None
    middle_pruned_marker: str = DEFAULT_MIDDLE_PRUNED_MARKER
    separator: str = "\n\n"


@dataclass(frozen=True, slots=True)
class _AdapterSettings:
    digest_ratio: float
    min_digest_bytes: int
    max_digest_bytes: int
    tail_min_groups: int
    input_guard_bytes: int


@dataclass(frozen=True, slots=True)
class _LogRecord:
    mode: str
    prompt_bytes: int
    limit_bytes: int
    prompt_prefix_sha256: str
    digested: int
    dropped: int
    reason: str = ""


def _load_settings(config_path: Path | None) -> _AdapterSettings:
    """Параметры компакции из long_session_config с безопасными дефолтами."""
    return _AdapterSettings(
        digest_ratio=read_float_setting(
            "history_compaction_digest_ratio",
            "AGY_HISTORY_COMPACTION_DIGEST_RATIO",
            0.20,
            (0.0, 1.0),
            config_path=config_path,
        ),
        min_digest_bytes=read_int_setting(
            "history_compaction_min_digest_bytes",
            "AGY_HISTORY_COMPACTION_MIN_DIGEST_BYTES",
            1024,
            (0, 1048576),
            config_path=config_path,
        ),
        max_digest_bytes=read_int_setting(
            "history_compaction_max_digest_bytes",
            "AGY_HISTORY_COMPACTION_MAX_DIGEST_BYTES",
            16384,
            (0, 1048576),
            config_path=config_path,
        ),
        tail_min_groups=read_int_setting(
            "history_compaction_tail_min_groups",
            "AGY_HISTORY_COMPACTION_TAIL_MIN_GROUPS",
            1,
            (0, 10000),
            config_path=config_path,
        ),
        input_guard_bytes=read_int_setting(
            "history_compaction_input_guard_bytes",
            "AGY_HISTORY_COMPACTION_INPUT_GUARD_BYTES",
            4194304,
            (0, 268435456),
            config_path=config_path,
        ),
    )


def _to_prompt_block(item: RawBlock, pos: int) -> PromptBlock:
    if isinstance(item, PromptBlock):
        return item
    if len(item) == 3:
        index, role, rendered = item
    else:
        role, rendered = item
        index = pos
    return PromptBlock(index=int(index), role=str(role), rendered=str(rendered))


def _to_prompt_blocks(raw: Sequence[RawBlock]) -> tuple[PromptBlock, ...]:
    return tuple(_to_prompt_block(item, pos) for pos, item in enumerate(raw))


def _measure(request: CompactionAdapterRequest, text: str) -> int:
    return (request.size_fn or json_text_bytes)(text)


def _prefix_sha256(blocks: Sequence[PromptBlock], separator: str) -> str:
    """SHA-256 якорного префикса (system* + первый user), как в домене."""
    return anchor_prefix_sha256(blocks, separator)


def _joined(blocks: Sequence[PromptBlock], request: CompactionAdapterRequest) -> str:
    parts = [block.rendered for block in blocks]
    if request.tail_block:
        parts.append(request.tail_block)
    return request.separator.join(parts).strip()


def _dropped_count(blocks: Sequence[PromptBlock], result: str) -> int:
    return sum(1 for block in blocks if block.rendered and block.rendered not in result)


def _emit(log_fn: Callable[[str], None] | None, record: _LogRecord) -> None:
    if log_fn:
        line = (
            f"history compaction: mode={record.mode} prompt_bytes={record.prompt_bytes} "
            f"limit={record.limit_bytes} prompt_prefix_sha256={record.prompt_prefix_sha256} "
            f"digested={record.digested} dropped={record.dropped}"
        )
        log_fn(line + (f" reason={record.reason}" if record.reason else ""))


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
) -> str:
    """Legacy-путь: результат делегата без изменений + структурированный лог."""
    result = request.legacy_prune(
        request.blocks, request.tail_block, request.limit_bytes
    )
    if mode == "fallback" or _changed_or_overflow(request, blocks, result):
        _emit(
            request.log_fn,
            _LogRecord(
                mode,
                _measure(request, result),
                request.limit_bytes,
                _prefix_sha256(blocks, request.separator),
                0,
                _dropped_count(blocks, result),
                reason,
            ),
        )
    return result


def _build_config(
    request: CompactionAdapterRequest, settings: _AdapterSettings
) -> CompactionConfig:
    """Доменный лимит из фактического limit_bytes минус обёртка и хвост."""
    overhead = (
        max(request.size_fn("") - json_text_bytes(""), 0) if request.size_fn else 0
    )
    tail_cost = (
        json_text_bytes(request.separator + request.tail_block)
        if request.tail_block
        else 0
    )
    effective = max(request.limit_bytes - overhead - tail_cost, 0)
    return CompactionConfig(
        limit_bytes=effective,
        digest_ratio=settings.digest_ratio,
        min_digest_bytes=settings.min_digest_bytes,
        max_digest_bytes=settings.max_digest_bytes,
        tail_min_groups=settings.tail_min_groups,
        middle_pruned_marker=request.middle_pruned_marker,
        separator=request.separator,
    )


def _with_tail(prompt: str, request: CompactionAdapterRequest) -> str:
    return request.separator.join(part for part in (prompt, request.tail_block) if part)


def _input_bytes(
    blocks: Sequence[PromptBlock], request: CompactionAdapterRequest
) -> int:
    total = sum(json_text_bytes(block.rendered) for block in blocks)
    return total + (json_text_bytes(request.tail_block) if request.tail_block else 0)


def _over_limit(request: CompactionAdapterRequest, prompt: str) -> bool:
    return max(json_text_bytes(prompt), _measure(request, prompt)) > request.limit_bytes


def _try_compact(
    request: CompactionAdapterRequest,
    blocks: tuple[PromptBlock, ...],
    settings: _AdapterSettings,
) -> tuple[str, CompactionResult]:
    result = compact_prompt_blocks(blocks, _build_config(request, settings))
    return _with_tail(result.prompt, request), result


def _compact_or_fallback(request: CompactionAdapterRequest) -> str:
    """Компакция при включённом флаге; гард/ошибка/переполнение — legacy."""
    try:
        blocks = _to_prompt_blocks(request.blocks)
    except Exception:
        return _run_legacy(request, (), "fallback", "compact_error")
    settings = _load_settings(request.config_path)
    if _input_bytes(blocks, request) > settings.input_guard_bytes:
        return _run_legacy(request, blocks, "fallback", "input_guard")
    try:
        prompt, result = _try_compact(request, blocks, settings)
    except Exception:
        return _run_legacy(request, blocks, "fallback", "compact_error")
    if _over_limit(request, prompt):
        return _run_legacy(request, blocks, "fallback", "over_limit")
    _emit(
        request.log_fn,
        _LogRecord(
            "compact",
            _measure(request, prompt),
            request.limit_bytes,
            result.prompt_prefix_sha256,
            result.digested_count,
            result.dropped_count,
        ),
    )
    return prompt


def _legacy_entry(request: CompactionAdapterRequest) -> str:
    return _run_legacy(request, _to_prompt_blocks(request.blocks), "legacy", "")


def render_or_compact_blocks(request: CompactionAdapterRequest) -> str:
    """Единая точка входа: legacy при ``enabled=False``, иначе компакция."""
    entry = _compact_or_fallback if request.enabled else _legacy_entry
    return entry(request)

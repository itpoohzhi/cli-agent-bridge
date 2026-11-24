"""Чистый домен детерминированной компакции истории диалога (AD-001)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .history_overflow_policy import OverflowSpec, shrink_overflow_parts
from .history_user_classifier import is_synthetic_user_block

DEFAULT_MIDDLE_PRUNED_MARKER = (
    "\n[... часть содержимого сообщения опущена мостом для соблюдения лимита"
    " контекста agy ...]\n"
)
_TOOL_REF_RE = re.compile(r"\[tool (?:call|result) ([^\]]+)\]")
DEFAULT_INPUT_GUARD_BYTES = 4 * 1024 * 1024

def json_text_bytes(text: str) -> int:
    """Байты UTF-8 строки после JSON-экранирования, без обрамляющих кавычек."""
    return len(json.dumps(text, ensure_ascii=False).encode("utf-8")) - 2
def _bsearch_max(high: int, fits: Callable[[int], bool]) -> int:
    low = 0
    while low < high:
        mid = (low + high + 1) // 2
        if fits(mid):
            low = mid
        else:
            high = mid - 1
    return low
def middle_prune_text(
    text: str,
    max_json_bytes: int,
    marker: str = DEFAULT_MIDDLE_PRUNED_MARKER,
) -> str:
    """Вырезать середину текста под экранированный байтовый бюджет."""
    if json_text_bytes(text) <= max_json_bytes:
        return text
    if json_text_bytes(marker) > max_json_bytes:
        keep = _bsearch_max(
            len(text), lambda n: json_text_bytes(text[:n]) <= max_json_bytes
        )
        return text[:keep]
    def build(keep: int) -> str:
        head = (keep + 1) // 2
        tail = keep // 2
        return text[:head] + marker + (text[-tail:] if tail else "")
    keep = _bsearch_max(
        len(text) - 1, lambda k: json_text_bytes(build(k)) <= max_json_bytes
    )
    return build(keep)

@dataclass(frozen=True, slots=True)
class PromptBlock:
    """Один отрендеренный блок промпта (``### N. role`` + тело)."""
    index: int
    role: str
    rendered: str
@dataclass(frozen=True, slots=True)
class CompactionConfig:
    """Бюджет и политики компакции; дефолты здесь — единственный SSOT."""
    limit_bytes: int
    digest_ratio: float = 0.20
    min_digest_bytes: int = 1024
    max_digest_bytes: int = 16384
    tail_min_groups: int = 1
    middle_pruned_marker: str = DEFAULT_MIDDLE_PRUNED_MARKER
    separator: str = "\n\n"
@dataclass(frozen=True, slots=True)
class CompactionResult:
    """Итог компакции: промпт, его размер, хэш префикса и счётчики."""
    prompt: str
    prompt_bytes: int
    limit_bytes: int
    prompt_prefix_sha256: str
    mode: str
    kept_count: int
    digested_count: int
    dropped_count: int

def _joined(blocks: Sequence[PromptBlock], separator: str) -> str:
    return separator.join(block.rendered for block in blocks)
def _group_blocks(blocks: Sequence[PromptBlock]) -> tuple[tuple[PromptBlock, ...], ...]:
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
    """Якорь до первого реального user; при его отсутствии — до любого user."""
    leading = 0
    in_leading = True
    for idx, group in enumerate(groups):
        if any(
            block.role == "user" and not is_synthetic_user_block(block.rendered)
            for block in group
        ):
            return idx + 1
    for idx, group in enumerate(groups):
        roles = [block.role for block in group]
        if "user" in roles:
            return idx + 1
        if in_leading and roles == ["system"]:
            leading += 1
        else:
            in_leading = False
    return leading
def _flatten(groups: Sequence[tuple[PromptBlock, ...]]) -> tuple[PromptBlock, ...]:
    return tuple(block for group in groups for block in group)
def _prefix_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
def anchor_prefix_sha256(blocks: Sequence[PromptBlock], separator: str) -> str:
    """SHA-256 якорного префикса блоков (system* + первый user)."""
    groups = _group_blocks(blocks)
    anchor = _flatten(groups[: _anchor_group_count(groups)])
    return _prefix_sha256(_joined(anchor, separator))

def _first_content_line(rendered: str, max_chars: int) -> str:
    lines = (line.strip() for line in rendered.splitlines())
    content = (s[:max_chars] for s in lines if s and not s.startswith("### "))
    return next(content, "")
def _digest_line(block: PromptBlock, max_chars: int) -> str:
    ids = [m.group(1) for m in _TOOL_REF_RE.finditer(block.rendered)]
    line = f"- #{block.index} {block.role}: {_first_content_line(block.rendered, max_chars)}"
    if ids:
        line += " [tools: " + ", ".join(dict.fromkeys(ids)) + "]"
    return line
def _digest_text(blocks: tuple[PromptBlock, ...], header: str, width: int) -> str:
    shown = [b for b in blocks if width or _TOOL_REF_RE.search(b.rendered)]
    return "\n".join([header] + [_digest_line(b, width) for b in shown])
def _compact_digest(blocks: tuple[PromptBlock, ...], header: str) -> str:
    found = [[m.group(1) for m in _TOOL_REF_RE.finditer(b.rendered)] for b in blocks]
    all_ids = [i for ids in found for i in dict.fromkeys(ids)]
    suffix = "\n- tool ids: " + ", ".join(dict.fromkeys(all_ids)) if all_ids else ""
    return header + suffix
def _build_digest(blocks: tuple[PromptBlock, ...], cfg: _DigestBudget) -> str:
    first, last = blocks[0].index, blocks[-1].index
    header = f"[сжатая история ходов {first}..{last}: {len(blocks)} сообщений]"
    compact = _compact_digest(blocks, header)
    widths = [_digest_text(blocks, header, width) for width in (120, 48, 0)]
    for candidate in [*widths, compact]:
        if json_text_bytes(candidate) <= cfg.budget:
            return candidate
    return middle_prune_text(compact, max(cfg.budget, 0), cfg.marker)
@dataclass(frozen=True, slots=True)
class _DigestBudget:
    budget: int
    marker: str
@dataclass(frozen=True, slots=True)
class _Layout:
    anchor: tuple[tuple[PromptBlock, ...], ...]
    middle: tuple[tuple[PromptBlock, ...], ...]
    tail: tuple[tuple[PromptBlock, ...], ...]
    carrier: tuple[PromptBlock, ...] | None

def _digest_budget(config: CompactionConfig) -> int:
    raw = int(config.limit_bytes * config.digest_ratio)
    capped = min(config.max_digest_bytes, max(config.min_digest_bytes, raw))
    return max(0, min(capped, config.limit_bytes))
def _has_user(group: tuple[PromptBlock, ...], real: bool = False) -> bool:
    return any(
        block.role == "user"
        and (not real or not is_synthetic_user_block(block.rendered))
        for block in group
    )
def _last_user_group(
    groups: Sequence[tuple[PromptBlock, ...]], real: bool
) -> tuple[PromptBlock, ...] | None:
    return next((group for group in reversed(groups) if _has_user(group, real)), None)
def _layout(
    groups: tuple[tuple[PromptBlock, ...], ...], config: CompactionConfig
) -> _Layout:
    anchor_n = _anchor_group_count(groups)
    anchor, rest = groups[:anchor_n], groups[anchor_n:]
    has_real = _last_user_group(groups, True) is not None
    carrier = _last_user_group(rest, True) if has_real else _last_user_group(groups, False)
    anchor_text = _joined(_flatten(anchor), config.separator)
    sep_bytes = json_text_bytes(config.separator)
    extra = _digest_budget(config) + 2 * sep_bytes if rest else 0
    min_tail = min(max(config.tail_min_groups, 0), len(rest))
    selected = set(rest[-min_tail:])
    if carrier in rest:
        selected.add(carrier)
    used = json_text_bytes(anchor_text) + extra
    used += sum(json_text_bytes(_joined(group, config.separator)) + sep_bytes for group in selected)
    for group in reversed(rest):
        if group in selected:
            continue
        cost = json_text_bytes(_joined(group, config.separator))
        if used + cost + sep_bytes <= config.limit_bytes:
            selected.add(group)
            used += cost + sep_bytes
        else:
            break
    middle = tuple(group for group in rest if group not in selected)
    tail = tuple(group for group in rest if group in selected)
    return _Layout(anchor, middle, tail, carrier)
def _assemble(layout: _Layout, config: CompactionConfig, digest: str) -> str:
    parts = [b.rendered for b in _flatten(layout.anchor)]
    if digest:
        parts.append(digest)
    parts += [b.rendered for b in _flatten(layout.tail)]
    return config.separator.join(parts)

def _demotion_candidate(layout: _Layout) -> tuple[PromptBlock, ...] | None:
    movable = [group for group in layout.tail if group != layout.carrier]
    synthetic = [
        group
        for group in movable
        if any(
            block.role == "user" and is_synthetic_user_block(block.rendered)
            for block in group
        )
    ]
    ordinary = [
        group
        for group in movable
        if not any("[tool call " in block.rendered for block in group)
    ]
    return next(iter(synthetic or ordinary), None)
def _demote(layout: _Layout, group: tuple[PromptBlock, ...]) -> _Layout:
    middle = tuple(sorted((*layout.middle, group), key=lambda item: item[0].index))
    return _Layout(
        layout.anchor,
        middle,
        tuple(item for item in layout.tail if item != group),
        layout.carrier,
    )
def _overflow_role(block: PromptBlock, carrier: tuple[PromptBlock, ...] | None) -> str:
    if (
        block.role == "user"
        and block not in (carrier or ())
        and is_synthetic_user_block(block.rendered)
    ):
        return "synthetic"
    return block.role

def _shrink_to_limit(layout: _Layout, config: CompactionConfig) -> tuple[str, _Layout]:
    budget = _digest_budget(config)
    if json_text_bytes(_assemble(layout, config, "")) > config.limit_bytes:
        budget = min(budget, max(config.min_digest_bytes, 512))
    marker = config.middle_pruned_marker
    current = layout
    while True:
        middle = _flatten(current.middle)
        digest = _build_digest(middle, _DigestBudget(budget, marker)) if middle else ""
        prompt = _assemble(current, config, digest)
        if json_text_bytes(prompt) <= config.limit_bytes:
            return prompt, current
        if candidate := _demotion_candidate(current):
            current = _demote(current, candidate)
            continue
        items = [
            (_overflow_role(b, current.carrier), b.rendered)
            for b in _flatten(current.anchor)
        ]
        if digest:
            items.append(("digest", digest))
        items += [
            (_overflow_role(b, current.carrier), b.rendered)
            for b in _flatten(current.tail)
        ]
        spec = OverflowSpec(
            max(config.limit_bytes, 0), config.separator, marker,
            json_text_bytes, middle_prune_text,
        )
        return shrink_overflow_parts(items, spec), current

def compact_prompt_blocks(
    blocks: Sequence[PromptBlock], config: CompactionConfig
) -> CompactionResult:
    """Сжать блоки истории под ``limit_bytes`` с сохранением якоря и хвоста."""
    prefix_hash = anchor_prefix_sha256(blocks, config.separator)
    full = _joined(blocks, config.separator)
    if json_text_bytes(full) <= config.limit_bytes:
        prompt, kept, digested = full, len(blocks), 0
    else:
        layout = _layout(_group_blocks(blocks), config)
        prompt, final = _shrink_to_limit(layout, config)
        kept = len(_flatten(final.anchor)) + len(_flatten(final.tail))
        digested = len(_flatten(final.middle))
        if final.carrier and len(final.tail) > 1 and any(b.rendered not in prompt for b in final.carrier):
            carrier_n = len(final.carrier)
            kept, digested = kept - carrier_n, digested + carrier_n
    size = json_text_bytes(prompt)
    return CompactionResult(
        prompt, size, config.limit_bytes, prefix_hash, "compact", kept, digested, 0
    )

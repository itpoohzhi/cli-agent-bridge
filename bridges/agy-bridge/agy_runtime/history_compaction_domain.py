"""Чистый домен структурированной компакции истории диалога (AD-001).

Детерминированная экстрактивная компакция: якорная голова (system + первое
сообщение пользователя) и хвост сохраняются дословно, середина заменяется
одним структурированным дайджестом с жёстким байтовым бюджетом. Пары
tool-call/tool-result неделимы. Без I/O, env, случайности и таймстампов.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

DEFAULT_MIDDLE_PRUNED_MARKER = (
    "\n[... часть содержимого сообщения опущена мостом для соблюдения лимита"
    " контекста agy ...]\n"
)
_TOOL_REF_RE = re.compile(r"\[tool (?:call|result) ([^\]]+)\]")


def json_text_bytes(text: str) -> int:
    """Байты UTF-8 строки после JSON-экранирования, без обрамляющих кавычек."""
    return len(json.dumps(text, ensure_ascii=False).encode("utf-8")) - 2


def _bsearch_max(high: int, fits: Callable[[int], bool]) -> int:
    """Наибольшее ``k`` из ``[0, high]``, где монотонный ``fits(k)`` истинен."""
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
    """Вырезать середину ``text`` с маркером под экранированный бюджет.

    Голова и хвост делятся поровну по символам; результат — наибольший,
    чей JSON-экранированный размер <= ``max_json_bytes``. Побайтово
    эквивалентна ``_middle_prune_text`` из ``server.py`` (VER-003).
    """
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
    """Бюджет и политики компакции; все параметры задаются адаптером."""

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
    """Атомарные группы: assistant с tool call + следующие tool-блоки."""
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
    """Число начальных групп якорной головы: system + первый user."""
    count = 0
    for group in groups:
        roles = [block.role for block in group]
        if roles == ["system"]:
            count += 1
            continue
        if "user" in roles:
            return count + 1
        break
    return count


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
    """Первая непустая строка тела без заголовка ``### N. role``."""
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
    """Дайджест одной ширины анонса; при ``width=0`` — только tool-блоки."""
    shown = [b for b in blocks if width or _TOOL_REF_RE.search(b.rendered)]
    return "\n".join([header] + [_digest_line(b, width) for b in shown])


def _compact_digest(blocks: tuple[PromptBlock, ...], header: str) -> str:
    """Минимальный дайджест: заголовок и все tool ids середины."""
    found = [[m.group(1) for m in _TOOL_REF_RE.finditer(b.rendered)] for b in blocks]
    all_ids = [i for ids in found for i in dict.fromkeys(ids)]
    suffix = "\n- tool ids: " + ", ".join(dict.fromkeys(all_ids)) if all_ids else ""
    return header + suffix


def _build_digest(blocks: tuple[PromptBlock, ...], cfg: _DigestBudget) -> str:
    """Структурированный дайджест середины в пределах байтового бюджета."""
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


def _digest_budget(config: CompactionConfig) -> int:
    raw = int(config.limit_bytes * config.digest_ratio)
    capped = min(config.max_digest_bytes, max(config.min_digest_bytes, raw))
    return max(0, min(capped, config.limit_bytes))


def _layout(
    groups: tuple[tuple[PromptBlock, ...], ...], config: CompactionConfig
) -> _Layout:
    """Разрезать группы на якорь, середину и максимально влезающий хвост."""
    anchor_n = _anchor_group_count(groups)
    anchor, rest = groups[:anchor_n], groups[anchor_n:]
    anchor_text = _joined(_flatten(anchor), config.separator)
    sep_bytes = json_text_bytes(config.separator)
    extra = _digest_budget(config) + 2 * sep_bytes if rest else 0
    reserve = json_text_bytes(anchor_text) + extra
    tail: list[tuple[PromptBlock, ...]] = []
    used = reserve
    for group in reversed(rest):
        cost = json_text_bytes(_joined(group, config.separator))
        cost += sep_bytes if tail else 0
        if tail and used + cost > config.limit_bytes:
            break
        tail.append(group)
        used += cost
    min_tail = min(max(config.tail_min_groups, 0), len(rest))
    tail.extend(reversed(rest[len(rest) - min_tail : len(rest) - len(tail)]))
    tail_t = tuple(reversed(tail))
    return _Layout(anchor, rest[: len(rest) - len(tail_t)], tail_t)


def _assemble(layout: _Layout, config: CompactionConfig, digest: str) -> str:
    parts = [b.rendered for b in _flatten(layout.anchor)]
    if digest:
        parts.append(digest)
    parts += [b.rendered for b in _flatten(layout.tail)]
    return config.separator.join(parts)


def _shrink_to_limit(layout: _Layout, config: CompactionConfig) -> tuple[str, _Layout]:
    """Собрать промпт и гарантировать ``<= limit`` управляемой деградацией."""
    budget = _digest_budget(config)
    marker = config.middle_pruned_marker
    current = layout
    budget_reduced = False
    while True:
        middle = _flatten(current.middle)
        digest = _build_digest(middle, _DigestBudget(budget, marker)) if middle else ""
        prompt = _assemble(current, config, digest)
        if json_text_bytes(prompt) <= config.limit_bytes:
            return prompt, current
        if len(current.tail) > 1:
            current = _Layout(
                current.anchor, current.middle + (current.tail[0],), current.tail[1:]
            )
            continue
        if middle and budget > 0 and not budget_reduced:
            excess = json_text_bytes(prompt) - config.limit_bytes
            budget = max(0, budget - excess)
            budget_reduced = True
            continue
        pruned = middle_prune_text(prompt, max(config.limit_bytes, 0), marker)
        return pruned, current


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
    size = json_text_bytes(prompt)
    return CompactionResult(
        prompt, size, config.limit_bytes, prefix_hash, "compact", kept, digested, 0
    )

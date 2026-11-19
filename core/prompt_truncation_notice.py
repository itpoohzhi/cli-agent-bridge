"""Чистый домен: уведомление модели об усечении активных tool-результатов.

Если при сжатии промпта под лимит активные (после последнего ``assistant``)
tool-результаты были усечены, к хвосту промпта добавляется короткое
фиксированное уведомление, чтобы модель не перечитывала файл целиком и
не уходила в цикл повторов. Модуль stateless, без I/O и без обращения к
окружению; в шаблон подставляются только целые числа.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

TRUNCATION_NOTICE_MARKER = "[truncation-notice]"

DEFAULT_TRUNCATION_NOTICE_TEMPLATE = (
    "\n\n[truncation-notice] {count} active tool result(s) were truncated "
    "to fit the {limit}-byte prompt limit. Do NOT re-read the same full "
    "file; use offset/limit chunks or targeted grep/rg instead."
)

_SEPARATOR = "\n\n"
_ROLE_TOOL = "tool"
_ROLE_ASSISTANT = "assistant"

Blocks = Sequence[tuple[int, str, str]]


@dataclass(frozen=True)
class NoticePolicy:
    """Политика уведомления: измеритель размера, шаблон и логгер статусов."""

    size_fn: Callable[[str], int]
    template: str | None = None
    log_fn: Callable[[str], None] | None = None


def count_truncated_active_tools(prompt: str, blocks: Blocks) -> int:
    """Число активных tool-блоков, не вошедших в ``prompt`` целиком."""
    last_assistant = -1
    for pos, (_, role, _) in enumerate(blocks):
        if role == _ROLE_ASSISTANT:
            last_assistant = pos
    active = blocks[last_assistant + 1 :]
    return sum(
        1 for _, role, text in active if role == _ROLE_TOOL and text not in prompt
    )


def _render_notice(template: str | None, count: int, limit: int) -> str:
    """Рендерит уведомление только из целых чисел с fail-safe на дефолт."""
    try:
        text = (template or DEFAULT_TRUNCATION_NOTICE_TEMPLATE).format(
            count=int(count), limit=int(limit)
        )
    except (KeyError, ValueError, IndexError):
        text = DEFAULT_TRUNCATION_NOTICE_TEMPLATE.format(
            count=int(count), limit=int(limit)
        )
    if text.startswith(_SEPARATOR):
        return text
    return _SEPARATOR + text.lstrip("\n")


def _notice_overhead(notice: str, size_fn: Callable[[str], int]) -> int:
    """Накладные расходы уведомления с запасом на экранирование ``size_fn``."""
    plain = size_fn(notice)
    marginal = size_fn("x" + notice) - size_fn("x")
    return max(plain, marginal, 0)


def _log(policy: NoticePolicy, status: str, count: int, limit: int) -> None:
    if policy.log_fn is not None:
        policy.log_fn(f"truncation_notice {status} count={count} limit={limit}")


def _build_candidate(
    notice: str,
    overhead: int,
    reprune: Callable[[int], str],
    size_fn: Callable[[str], int],
    limit: int,
) -> str | None:
    """Собирает кандидата с одним уточняющим проходом; None, если не влезло."""
    candidate = reprune(limit - overhead) + notice
    size = size_fn(candidate)
    if size <= limit:
        return candidate
    budget = limit - overhead - (size - limit)
    if budget <= 0:
        return None
    retry = reprune(budget) + notice
    return retry if size_fn(retry) <= limit else None


def with_truncation_notice(
    prompt: str,
    blocks: Blocks,
    reprune: Callable[[int], str],
    policy: NoticePolicy,
    limit: int,
) -> str:
    """Добавляет уведомление об усечении активных tool-результатов в хвост.

    Без усечения активных tool-блоков возвращает ``prompt`` без изменений
    и не вызывает ``reprune``. Если уведомление не помещается в ``limit`` —
    возвращает исходный ``prompt``.
    """
    truncated = count_truncated_active_tools(prompt, blocks)
    if truncated == 0:
        return prompt
    notice = _render_notice(policy.template, truncated, limit)
    overhead = _notice_overhead(notice, policy.size_fn)
    result = None
    if limit > overhead:
        result = _build_candidate(notice, overhead, reprune, policy.size_fn, limit)
    if result is None:
        _log(policy, "skipped_no_room", truncated, limit)
        return prompt
    _log(policy, "applied", truncated, limit)
    return result

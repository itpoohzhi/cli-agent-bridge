"""Чистая Zero-I/O политика подавления пост-вызовного вывода и ошибок live-парсера."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Protocol


class PostCallState(str, Enum):
    """Состояния FSM пост-вызовной санитизации потока."""

    ACTIVE = "active"
    POST_CALL_SUPPRESSED = "post_call_suppressed"
    FAILED = "failed"


class PostCallEvent(str, Enum):
    """События потока, оцениваемые PostCallFSM."""

    TEXT_CHUNK = "text_chunk"
    TOOL_OPEN = "tool_open"
    TOOL_CALL_EMITTED = "tool_call_emitted"
    ORPHAN_TOOL_CLOSE = "orphan_tool_close"
    ORPHAN_REASONING_CLOSE = "orphan_reasoning_close"
    ORPHAN_OTHER_SERVICE_TAG = "orphan_other_service_tag"
    UNCLOSED_AT_EOF = "unclosed_at_eof"
    EOF = "eof"


class PostCallAction(str, Enum):
    """Побочные действия, предписываемые решением PostCallFSM."""

    CONTINUE = "continue"
    LOG_CUTOFF_ONCE = "log_cutoff_once"
    CLEAR_TAIL_BUF = "clear_tail_buf"
    DROP_SILENTLY = "drop_silently"
    RAISE_PARSE_ERROR = "raise_parse_error"
    FINISH_CLEAN = "finish_clean"


@dataclass(frozen=True, slots=True)
class PostCallPolicy:
    """Конфигурация политики пост-вызовного отсечения и окна диагностики."""

    cutoff_enabled: bool = False
    diagnostic_window_chars: int = 120
    diagnostic_redact_margin_chars: int = 2048


@dataclass(frozen=True, slots=True)
class PostCallContext:
    """Снимок контекста потока в момент оценки перехода FSM."""

    cutoff_enabled: bool
    strict_live: bool
    reject_tools: bool
    has_open_block: bool
    calls_count: int


@dataclass(frozen=True, slots=True)
class PostCallDecision:
    """Иммутабельный результат перехода PostCallFSM."""

    next_state: PostCallState
    actions: tuple[PostCallAction, ...] = ()
    reason: str = ""

    @property
    def log_cutoff_once(self) -> bool:
        return PostCallAction.LOG_CUTOFF_ONCE in self.actions

    @property
    def clear_tail_buf(self) -> bool:
        return PostCallAction.CLEAR_TAIL_BUF in self.actions

    @property
    def drop_silently(self) -> bool:
        return PostCallAction.DROP_SILENTLY in self.actions

    @property
    def raise_parse_error(self) -> bool:
        return PostCallAction.RAISE_PARSE_ERROR in self.actions

    @property
    def clean_complete(self) -> bool:
        return PostCallAction.FINISH_CLEAN in self.actions


class TransitionRule(Protocol):
    def __call__(self, ctx: PostCallContext, /) -> PostCallDecision: ...


_ACTIVE_CONTINUE: Final = PostCallDecision(PostCallState.ACTIVE, (PostCallAction.CONTINUE,))
_SUPPRESSED_CUTOFF: Final = PostCallDecision(
    PostCallState.POST_CALL_SUPPRESSED,
    (PostCallAction.LOG_CUTOFF_ONCE, PostCallAction.CLEAR_TAIL_BUF, PostCallAction.DROP_SILENTLY),
    "post_call_orphan_tool_close",
)
_SUPPRESSED_DROP: Final = PostCallDecision(
    PostCallState.POST_CALL_SUPPRESSED, (PostCallAction.DROP_SILENTLY,)
)
_SUPPRESSED_EOF: Final = PostCallDecision(
    PostCallState.POST_CALL_SUPPRESSED, (PostCallAction.FINISH_CLEAN,)
)
_FAILED_PARSE: Final = PostCallDecision(
    PostCallState.FAILED, (PostCallAction.RAISE_PARSE_ERROR,)
)


def _active_continue(_ctx: PostCallContext) -> PostCallDecision:
    return _ACTIVE_CONTINUE


def _active_unclosed(_ctx: PostCallContext) -> PostCallDecision:
    return _FAILED_PARSE


def _active_orphan_tool_close(ctx: PostCallContext) -> PostCallDecision:
    if not (ctx.strict_live or ctx.reject_tools):
        return _ACTIVE_CONTINUE
    if ctx.cutoff_enabled and not ctx.has_open_block and ctx.calls_count >= 1:
        return _SUPPRESSED_CUTOFF
    return _FAILED_PARSE


def _active_orphan_reasoning_close(ctx: PostCallContext) -> PostCallDecision:
    return _FAILED_PARSE if ctx.strict_live else _ACTIVE_CONTINUE


def _active_orphan_other_tag(ctx: PostCallContext) -> PostCallDecision:
    return _FAILED_PARSE if (ctx.strict_live or ctx.reject_tools) else _ACTIVE_CONTINUE


def _suppressed_drop(_ctx: PostCallContext) -> PostCallDecision:
    return _SUPPRESSED_DROP


def _suppressed_eof(_ctx: PostCallContext) -> PostCallDecision:
    return _SUPPRESSED_EOF


def _failed_always(_ctx: PostCallContext) -> PostCallDecision:
    return _FAILED_PARSE


def _build_transitions() -> Mapping[tuple[PostCallState, PostCallEvent], TransitionRule]:
    table: dict[tuple[PostCallState, PostCallEvent], TransitionRule] = {
        (PostCallState.ACTIVE, PostCallEvent.TEXT_CHUNK): _active_continue,
        (PostCallState.ACTIVE, PostCallEvent.TOOL_OPEN): _active_continue,
        (PostCallState.ACTIVE, PostCallEvent.TOOL_CALL_EMITTED): _active_continue,
        (PostCallState.ACTIVE, PostCallEvent.ORPHAN_TOOL_CLOSE): _active_orphan_tool_close,
        (PostCallState.ACTIVE, PostCallEvent.ORPHAN_REASONING_CLOSE): _active_orphan_reasoning_close,
        (PostCallState.ACTIVE, PostCallEvent.ORPHAN_OTHER_SERVICE_TAG): _active_orphan_other_tag,
        (PostCallState.ACTIVE, PostCallEvent.UNCLOSED_AT_EOF): _active_unclosed,
        (PostCallState.ACTIVE, PostCallEvent.EOF): _active_continue,
    }
    for event in PostCallEvent:
        table[(PostCallState.POST_CALL_SUPPRESSED, event)] = (
            _suppressed_eof if event is PostCallEvent.EOF else _suppressed_drop
        )
        table[(PostCallState.FAILED, event)] = _failed_always
    return MappingProxyType(table)


POST_CALL_TRANSITIONS: Final[Mapping[tuple[PostCallState, PostCallEvent], TransitionRule]] = (
    _build_transitions()
)


class PostCallFSM:
    """Конечный автомат пост-вызовного подавления (3 состояния x 8 событий)."""

    @staticmethod
    def decide(
        state: PostCallState,
        event: PostCallEvent,
        ctx: PostCallContext,
    ) -> PostCallDecision:
        """Вычисляет детерминированный переход для пары `(state, event)`."""
        return POST_CALL_TRANSITIONS[(state, event)](ctx)


def format_live_parser_error_log(
    error: Exception | str,
    *,
    stage: str = "live",
    redact_fn: Callable[[str], str] | None = None,
    max_chars: int = 512,
) -> str:
    """Форматирует и редактирует сообщение ошибки live-парсера через DI `redact_fn`."""
    raw_msg = str(error)
    clean_msg = redact_fn(raw_msg) if redact_fn is not None else raw_msg
    bounded_stage = stage.strip() or "live"
    limit = max(1, max_chars)
    if len(clean_msg) > limit:
        clean_msg = clean_msg[:limit] + "..."
    return f"live_parser_error stage={bounded_stage} detail={clean_msg!r}"

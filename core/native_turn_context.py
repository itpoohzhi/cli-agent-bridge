from __future__ import annotations

# Immutable DTO нативного turn-контекста (messages/tools/tool_choice/cache key).
# Чистый zero-IO модуль: снимает глубокие копии полей исходного HTTP JSON-запроса
# до удаления scratch-полей и отдаёт наружу только копии.

import copy
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import cast

_CURRENT_NATIVE_PAYLOAD: ContextVar[NativeTurnPayload | None] = ContextVar(
    "current_native_turn_payload", default=None
)


def get_current_native_payload() -> NativeTurnPayload | None:
    """Текущий `NativeTurnPayload` активного HTTP-хода (или `None`)."""
    return _CURRENT_NATIVE_PAYLOAD.get()


@contextmanager
def native_payload_scope(payload: NativeTurnPayload | None) -> Iterator[None]:
    """Ограничивает `NativeTurnPayload` текущим ходом и безусловно сбрасывает его на выходе."""
    token = _CURRENT_NATIVE_PAYLOAD.set(payload)
    try:
        yield
    finally:
        _CURRENT_NATIVE_PAYLOAD.reset(token)


@dataclass(frozen=True)
class NativeTurnPayload:
    """Снимок нативных полей запроса; внутреннее состояние не мутируется снаружи."""

    messages: tuple[dict[str, object], ...] = ()
    tools: tuple[dict[str, object], ...] = ()
    tool_choice: object = None
    prompt_cache_key: str | None = None
    stream_options: dict[str, object] | None = None

    def to_messages_list(self) -> list[dict[str, object]]:
        """Глубокая копия messages как список."""
        return [copy.deepcopy(m) for m in self.messages]

    def to_tools_list(self) -> list[dict[str, object]]:
        """Глубокая копия tools как список."""
        return [copy.deepcopy(t) for t in self.tools]

    def to_tool_choice(self) -> object:
        """Глубокая копия tool_choice."""
        return copy.deepcopy(self.tool_choice)

    def to_stream_options(self) -> dict[str, object] | None:
        """Глубокая копия stream_options."""
        return copy.deepcopy(self.stream_options)


def _dict_items(value: object) -> tuple[dict[str, object], ...]:
    items = cast(list[object], value) if isinstance(value, list) else []
    return tuple(
        copy.deepcopy(cast(dict[str, object], i)) for i in items if isinstance(i, dict)
    )


def build_native_turn_payload(
    body: Mapping[str, object] | None,
) -> NativeTurnPayload | None:
    """Снять payload из исходного тела запроса; `None`, если полезных полей нет."""
    if not isinstance(body, Mapping):
        return None
    key = body.get("prompt_cache_key")
    raw_options = body.get("stream_options")
    options = (
        cast(dict[str, object], raw_options) if isinstance(raw_options, dict) else None
    )
    payload = NativeTurnPayload(
        messages=_dict_items(body.get("messages")),
        tools=_dict_items(body.get("tools")),
        tool_choice=copy.deepcopy(body.get("tool_choice")),
        prompt_cache_key=key if isinstance(key, str) and key else None,
        stream_options=copy.deepcopy(options),
    )
    return payload if payload != NativeTurnPayload() else None

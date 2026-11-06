from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


@dataclass
class SlotConfig:
    adapter: str
    backend_id: str
    effort: str | None
    profile: str | None
    mode: str
    pool_size: int
    startup_timeout_s: float
    turn_timeout_s: float


@dataclass
class TurnRequest:
    prompt: Any
    stream: bool
    timeout_s: float
    options: dict[str, Any]


@dataclass
class TurnResult:
    content: str
    reasoning_content: str | None
    tool_calls: list[Any]
    finish_reason: str
    usage: dict[str, int]


class AdapterCapabilities(TypedDict):
    supportsPersistentProcess: bool
    supportsLogicalSessions: bool
    supportsContextReset: bool
    supportsEffortMutation: bool
    supportsConcurrentTurns: bool
    supportsHealthProbe: bool
    supportsWarmup: bool


class ResidentAdapter(Protocol):
    async def start(self, cfg: SlotConfig) -> Any:
        ...

    async def wait_ready(self, handle: Any, timeout_s: float) -> None:
        ...

    async def warmup(
        self,
        handle: Any,
        model: str,
        effort: str | None,
    ) -> None:
        ...

    async def reset_context(self, handle: Any) -> None:
        ...

    async def apply_or_verify_effort(
        self,
        handle: Any,
        effort: str | None,
    ) -> None:
        ...

    async def execute_turn(
        self,
        handle: Any,
        req: TurnRequest,
    ) -> TurnResult:
        ...

    async def health_check(self, handle: Any) -> bool:
        ...

    async def shutdown(self, handle: Any) -> None:
        ...

    def runtime_identity(self, handle: Any) -> dict[str, Any]:
        ...


__all__ = [
    "SlotConfig",
    "TurnRequest",
    "TurnResult",
    "AdapterCapabilities",
    "ResidentAdapter",
]

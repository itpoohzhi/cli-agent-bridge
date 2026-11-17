"""Universal agent-agnostic stdio resident process pool core."""

# fmt: off
from .types import (
    ExecutionFingerprint, ResidentProcessInfo, SlotAffinityKey, SlotAllocation,
    SlotEffect, SlotEvent, SlotState, StdioTurnState, step_slot_fsm,
)

__all__ = [
    "ExecutionFingerprint", "ResidentProcessInfo", "SlotAffinityKey",
    "SlotAllocation", "SlotEffect", "SlotEvent", "SlotState",
    "StdioTurnState", "step_slot_fsm",
]
# fmt: on

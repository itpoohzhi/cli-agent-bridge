"""Active passthrough turns (ADR-0015 AD-003)."""

from __future__ import annotations

import hmac
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from core.liveness_signals import LivenessSnapshot, LivenessWindow
from core.turn_session_manager import SNAPSHOT_SCHEMA_VERSION


@dataclass(frozen=True)
class _Entry:
    owner_token_hash: str
    window: LivenessWindow


def new_passthrough_turn_id() -> str:
    """Id matching TURN_ID_RE."""
    return "pt-" + uuid.uuid4().hex


class LivenessRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    def register(self, turn_id: str, owner_token_hash: str, window: LivenessWindow) -> None:
        with self._lock:
            self._entries[turn_id] = _Entry(owner_token_hash, window)

    def finish(self, turn_id: str) -> bool:
        with self._lock:
            return self._entries.pop(turn_id, None) is not None

    def get_snapshot(self, turn_id: str, owner_token_hash: str) -> LivenessSnapshot:
        with self._lock:
            entry = self._entries.get(turn_id)
            if entry is None:
                raise KeyError(turn_id)
            if not hmac.compare_digest(entry.owner_token_hash.encode(), owner_token_hash.encode()):
                raise PermissionError(turn_id)
            return entry.window.snapshot()

    def turn_snapshot(self, turn_id: str, owner_token_hash: str) -> dict[str, Any]:
        live = self.get_snapshot(turn_id, owner_token_hash).to_wire()
        return {
            "schema_version": SNAPSHOT_SCHEMA_VERSION, "turn_id": turn_id, "backend": "passthrough",
            "status": "running_attached", "state": "RUNNING_ATTACHED", "liveness": live,
        }

    def active_count(self) -> int:
        with self._lock:
            return len(self._entries)


_REGISTRY = LivenessRegistry()


def get_registry() -> LivenessRegistry:
    return _REGISTRY

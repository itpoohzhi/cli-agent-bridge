from __future__ import annotations

from pathlib import Path

from core.activity_window import ActivityWindow
import sys
BRIDGE_DIR = Path(__file__).resolve().parents[1] / "bridges" / "muse-bridge"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))
from muse_runtime.activity import MuseServeMessageReader  # noqa: E402


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_touch_extends_idle_deadline() -> None:
    clock = FakeClock()
    window = ActivityWindow(idle_timeout_s=5.0, safety_cap_s=12.0, clock=clock)

    assert window.idle_deadline == 5.0

    clock.now = 3.0
    window.touch()
    assert window.idle_deadline == 8.0

    clock.now = 7.0
    window.touch()
    assert window.idle_deadline == 12.0


def test_touch_clamped_by_safety_deadline() -> None:
    clock = FakeClock()
    window = ActivityWindow(idle_timeout_s=5.0, safety_cap_s=12.0, clock=clock)

    clock.now = 10.0
    window.touch()
    assert window.idle_deadline == 12.0
    assert window.safety_deadline == 12.0


def test_expired_after_deadline() -> None:
    clock = FakeClock()
    window = ActivityWindow(idle_timeout_s=5.0, safety_cap_s=12.0, clock=clock)

    assert not window.is_expired()

    clock.now = 5.0
    assert window.is_expired()


def test_expired_after_safety_cap_even_with_touch_before() -> None:
    clock = FakeClock()
    window = ActivityWindow(idle_timeout_s=5.0, safety_cap_s=12.0, clock=clock)

    for t in (3, 7, 10):
        clock.now = float(t)
        window.touch()

    assert window.idle_deadline == 12.0

    clock.now = 11.0
    assert not window.is_expired()

    clock.now = 12.0
    assert window.is_expired()


def test_reader_touches_only_on_useful_chunks() -> None:
    written = []
    reader = MuseServeMessageReader(on_useful_chunk=lambda: written.append(1))

    # Empty content -> not useful
    reader.feed(b'{"content": ""}\n')
    # Content -> useful
    reader.feed(b'{"content": "hi"}\n')
    # Reasoning only -> useful
    reader.feed(b'{"reasoning_content": "thinking"}\n')
    # Tool calls -> useful
    reader.feed(b'{"tool_calls": [{"id": "1"}]}\n')
    # Protocol only -> not useful
    reader.feed(b'{"method": "ready", "params": {}}\n')

    assert len(written) == 3


def test_reader_ignores_invalid_json() -> None:
    written = []
    reader = MuseServeMessageReader(on_useful_chunk=lambda: written.append(1))

    reader.feed(b'not json\n')
    reader.feed(b'{"content": "ok"}\n')

    assert len(written) == 1

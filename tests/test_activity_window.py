import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "muse-bridge"
for p in (str(ROOT), str(BRIDGE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from core.activity_window import SlidingActivityWindow  # noqa: E402
from core.backpressure import BridgeBackpressureError, BoundedBridgeWriteQueue  # noqa: E402
from muse_runtime.activity import MuseServeMessageReader  # noqa: E402


def test_activity_window_extends_idle_deadline_and_clamps_to_safety_cap():
    window = SlidingActivityWindow(idle_timeout_s=0.05, safety_cap_s=0.12)
    first_deadline = window.idle_deadline
    assert first_deadline is not None
    time.sleep(0.03)
    window.touch()
    second_deadline = window.idle_deadline
    assert second_deadline >= first_deadline
    assert second_deadline - time.monotonic() <= 0.12 + 1e-6
    time.sleep(0.13)
    assert window.expired is True


def test_message_reader_buffers_lines_and_touches_only_useful_chunks():
    touches = []
    reader = MuseServeMessageReader(on_useful_chunk=lambda: touches.append(1))
    chunks = [b'{"a":', b"1}\n", b"  ", b"\n", b'{"b":2}\n']
    messages = []
    for chunk in chunks:
        messages.extend(reader.feed(chunk))
    messages.extend(reader.flush())
    assert messages == ['{"a":1}', '{"b":2}']
    assert len(touches) >= 2


def test_bounded_bridge_write_queue_raises_typed_error_and_recovers():
    q = BoundedBridgeWriteQueue(maxsize=1)
    q.put({"x": 1}, timeout=0.1)
    with pytest.raises(BridgeBackpressureError):
        q.put({"x": 2}, timeout=0.01)
    assert q.get(timeout=0.1) == {"x": 1}
    q.put({"x": 3}, timeout=0.1)
    assert q.get(timeout=0.1) == {"x": 3}

from __future__ import annotations

from core.activity_window import ActivityWindow, MessageReader


def test_message_reader_buffers_lines_and_touches_only_useful_chunks() -> None:
    times = iter([0.0, 0.0, 1.0, 2.0, 3.0])
    window = ActivityWindow(
        idle_timeout_s=5.0, safety_cap_s=3600.0, clock=lambda: next(times)
    )
    reader = MessageReader(window)
    chunks = [b'{"content":"alpha"}\n', b"  \n", b'{"reasoning_content":"beta"}\n']
    result = reader.read(chunks)
    assert result == [chunks[0], chunks[2]]

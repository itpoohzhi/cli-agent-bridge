# ruff: noqa: E402, I001
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
for _p in (str(BRIDGE_DIR), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agy_runtime.history_overflow_policy import (
    EVICT_ROLE_ORDER,
    OverflowSpec,
    shrink_overflow_parts,
)


def json_text_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def middle_prune_text(text: str, limit_bytes: int, marker: str) -> str:
    if limit_bytes <= 0:
        return ""
    if json_text_bytes(text) <= limit_bytes:
        return text
    if json_text_bytes(marker) >= limit_bytes:
        return marker[:limit_bytes]
    content_bytes = limit_bytes - json_text_bytes(marker)
    left_bytes = (content_bytes + 1) // 2
    right_bytes = content_bytes - left_bytes
    tail = text[-right_bytes:] if right_bytes else ""
    return f"{text[:left_bytes]}{marker}{tail}"


class PruneSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def __call__(self, text: str, limit_bytes: int, marker: str) -> str:
        self.calls.append((text, limit_bytes, marker))
        return middle_prune_text(text, limit_bytes, marker)


def _block(label: str, size: int) -> str:
    frame = f"<{label}>"
    filler = "x" * (size - (2 * len(frame)))
    return f"{frame}{filler}{frame}"


def _shrink(
    items: list[tuple[str, str]], limit_bytes: int, spy: PruneSpy
) -> str:
    spec = OverflowSpec(
        limit_bytes, "\n", "<cut>", json_text_bytes, spy
    )
    return shrink_overflow_parts(items, spec)


def test_tool_eviction_preserves_systems_and_user_task() -> None:
    systems = [_block(f"SYS-{index}", 200) for index in range(3)]
    user = _block("USER-TASK", 196)
    tools = [_block(f"TOOL-{index}", 200) for index in range(3)]
    items = [
        *(("system", text) for text in systems),
        ("user", user),
        *(("tool", text) for text in tools),
    ]
    spy = PruneSpy()

    prompt = _shrink(items, 1000, spy)

    assert json_text_bytes(prompt) <= 1000
    assert user in prompt
    assert all(system in prompt for system in systems)
    assert tools[0] not in prompt
    assert tools[1] not in prompt
    assert tools[2] in prompt
    assert spy.calls == []


def test_eviction_cascades_and_shrinks_last_needed_system() -> None:
    systems = [_block(f"S{index}", 200) for index in range(4)]
    assistant = _block("ASSISTANT", 150)
    user = _block("USER", 150)
    tools = [_block(f"T{index}", 200) for index in range(2)]
    items = [
        *(("system", text) for text in systems),
        ("assistant", assistant),
        ("user", user),
        *(("tool", text) for text in tools),
    ]
    spy = PruneSpy()

    prompt = _shrink(items, 700, spy)

    assert json_text_bytes(prompt) == 700
    assert all(tool not in prompt for tool in tools)
    assert assistant not in prompt
    assert user in prompt
    assert systems[0] not in prompt
    assert systems[1] not in prompt
    assert prompt.count("<S1>") == 2
    assert systems[2] in prompt
    assert systems[3] in prompt
    assert spy.calls == [(systems[1], 147, "<cut>")]


def test_user_shrinks_after_short_tools_are_evicted() -> None:
    user = _block("USER-LONG", 240)
    tools = [_block(f"SHORT-{index}", 100) for index in range(2)]
    items = [("user", user), *(("tool", text) for text in tools)]
    spy = PruneSpy()

    prompt = _shrink(items, 180, spy)

    assert json_text_bytes(prompt) == 180
    assert all(tool not in prompt for tool in tools)
    assert prompt.startswith("<USER-LONG>")
    assert prompt.endswith("<USER-LONG>")
    assert "<cut>" in prompt
    assert spy.calls == [(user, 180, "<cut>")]


def test_low_priority_eviction_order_excludes_user() -> None:
    assert EVICT_ROLE_ORDER == ("tool", "digest", "assistant", "system")


def test_eviction_and_shrink_boundary_exits_zero_avail() -> None:
    spy_z1 = PruneSpy()
    assert _shrink([("system", "A" * 9), ("tool", "B" * 300)], 10, spy_z1) == "A" * 9
    assert spy_z1.calls == [("B" * 300, 0, "<cut>")]

    spy_z2 = PruneSpy()
    tool_big = _block("TB", 150)
    tool_exact = _block("TZ", 100)
    res_z2 = _shrink(
        [("system", _block("SZ", 200)), ("user", _block("UZ", 198)), ("tool", tool_big), ("tool", tool_exact)],
        400,
        spy_z2,
    )
    assert json_text_bytes(res_z2) <= 400
    assert spy_z2.calls == [(tool_exact, 0, "<cut>")]

    seen_u: list[str] = []

    def spy_size(text: str) -> int:
        seen_u.append(text)
        return json_text_bytes(text)

    spec1 = OverflowSpec(300, "\n", "<cut>", spy_size, middle_prune_text)
    fitted1 = shrink_overflow_parts([("user", "U" * 500)], spec1)
    assert seen_u.count(fitted1) == 1

    seen_u.clear()
    user_blk = "U" * 150
    spec2 = OverflowSpec(150, "\n", "<cut>", spy_size, middle_prune_text)
    fitted2 = shrink_overflow_parts([("system", "S" * 150), ("user", user_blk)], spec2)
    assert fitted2 == user_blk
    assert seen_u.count(user_blk) == 5

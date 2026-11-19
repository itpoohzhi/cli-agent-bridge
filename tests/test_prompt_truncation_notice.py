"""Тесты чистого домена core.prompt_truncation_notice."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.prompt_truncation_notice import (
    DEFAULT_TRUNCATION_NOTICE_TEMPLATE,
    TRUNCATION_NOTICE_MARKER,
    NoticePolicy,
    count_truncated_active_tools,
    with_truncation_notice,
)


def _bytes(text: str) -> int:
    return len(text.encode("utf-8"))


class _Reprune:
    """Фейковый сжиматель: якоря целиком, хвост последнего блока режется."""

    def __init__(self, anchors: str, tail: str) -> None:
        self.anchors = anchors
        self.tail = tail
        self.budgets: list[int] = []

    def __call__(self, budget: int) -> str:
        self.budgets.append(budget)
        room = max(budget - _bytes(self.anchors), 0)
        return self.anchors + self.tail[:room]


def _policy(**kwargs: object) -> NoticePolicy:
    return NoticePolicy(size_fn=_bytes, **kwargs)  # type: ignore[arg-type]


def _no_call(budget: int) -> str:
    raise AssertionError(f"reprune must not be called: {budget}")


def test_default_template_fits_size_budget() -> None:
    assert TRUNCATION_NOTICE_MARKER in DEFAULT_TRUNCATION_NOTICE_TEMPLATE
    assert len(DEFAULT_TRUNCATION_NOTICE_TEMPLATE.encode("utf-8")) <= 300
    rendered = DEFAULT_TRUNCATION_NOTICE_TEMPLATE.format(count=99, limit=1_000_000)
    assert len(rendered.encode("utf-8")) <= 300


def test_no_truncation_returns_prompt_unchanged() -> None:
    blocks = [(0, "system", "SYS"), (1, "tool", "TOOL")]
    prompt = "SYS\n\nTOOL"
    result = with_truncation_notice(prompt, blocks, _no_call, _policy(), 1000)
    assert result == prompt


def test_truncated_history_tool_only_adds_no_notice() -> None:
    blocks = [
        (0, "tool", "OLD-TOOL-RESULT"),
        (1, "assistant", "ok"),
        (2, "tool", "NEW"),
    ]
    prompt = "ok\n\nNEW"
    assert count_truncated_active_tools(prompt, blocks) == 0
    assert with_truncation_notice(prompt, blocks, _no_call, _policy(), 1000) == prompt


def test_no_assistant_means_all_tools_are_active() -> None:
    blocks = [(0, "tool", "AAAA"), (1, "tool", "BBBB"), (2, "user", "u")]
    assert count_truncated_active_tools("AAAA", blocks) == 1
    assert count_truncated_active_tools("", blocks) == 2


def test_one_active_tool_truncated_appends_single_notice() -> None:
    system, tool = "S" * 61_000, "T" * 60_000
    blocks = [(0, "system", system), (1, "tool", tool)]
    limit = 98_304
    prompt = system + tool[:30_000]
    reprune = _Reprune(system, tool)
    logs: list[str] = []
    policy = _policy(log_fn=logs.append)

    result = with_truncation_notice(prompt, blocks, reprune, policy, limit)

    assert result.count(TRUNCATION_NOTICE_MARKER) == 1
    assert _bytes(result) <= limit
    assert "1 active tool result(s)" in result
    assert f"{limit}-byte" in result
    assert result.endswith("instead.")
    assert logs == [f"truncation_notice applied count=1 limit={limit}"]


def test_two_active_tools_truncated_counted() -> None:
    blocks = [
        (0, "system", "SYS"),
        (1, "tool", "A" * 500),
        (2, "tool", "B" * 500),
    ]
    prompt = "SYS" + "A" * 100 + "B" * 100
    reprune = _Reprune("SYS", "A" * 100)
    result = with_truncation_notice(prompt, blocks, reprune, _policy(), 2000)
    assert "2 active tool result(s)" in result
    assert result.count(TRUNCATION_NOTICE_MARKER) == 1
    assert _bytes(result) <= 2000


def test_notice_separated_by_blank_line() -> None:
    blocks = [(0, "tool", "X" * 100)]
    template = "no-sep {count}/{limit}"
    reprune = _Reprune("", "X" * 100)
    result = with_truncation_notice(
        "X", blocks, reprune, _policy(template=template), 500
    )
    assert result.endswith("\n\nno-sep 1/500")


def test_degenerate_anchors_leave_no_room_returns_prompt() -> None:
    anchors = "S" * 400
    blocks = [(0, "system", anchors), (1, "tool", "T" * 400)]
    prompt = anchors + "T" * 50
    logs: list[str] = []
    limit = 500
    reprune = _Reprune(anchors, "T" * 400)
    result = with_truncation_notice(
        prompt, blocks, reprune, _policy(log_fn=logs.append), limit
    )
    assert result == prompt
    assert _bytes(result) <= limit
    assert TRUNCATION_NOTICE_MARKER not in result
    assert logs == [f"truncation_notice skipped_no_room count=1 limit={limit}"]


def test_limit_not_above_notice_overhead_returns_prompt() -> None:
    blocks = [(0, "tool", "T" * 100)]
    result = with_truncation_notice("T", blocks, _no_call, _policy(), 10)
    assert result == "T"


def test_custom_template_is_used() -> None:
    blocks = [(0, "tool", "T" * 100)]
    template = "\n\n[custom] {count} cut at {limit}"
    reprune = _Reprune("", "T" * 100)
    result = with_truncation_notice(
        "T", blocks, reprune, _policy(template=template), 300
    )
    assert result.endswith("\n\n[custom] 1 cut at 300")
    assert TRUNCATION_NOTICE_MARKER not in result


def test_broken_template_falls_back_to_default() -> None:
    blocks = [(0, "tool", "T" * 100)]
    for broken in ("{unknown}", "{", "{0}"):
        reprune = _Reprune("", "T" * 100)
        policy = _policy(template=broken)
        result = with_truncation_notice("T", blocks, reprune, policy, 1000)
        assert result.count(TRUNCATION_NOTICE_MARKER) == 1
        assert "1 active tool result(s)" in result


def test_block_text_is_never_interpolated() -> None:
    evil = "{count}{limit}{0}%s" + "Z" * 100
    blocks = [(0, "tool", evil)]
    reprune = _Reprune("", evil)
    logs: list[str] = []
    result = with_truncation_notice(
        "Z", blocks, reprune, _policy(log_fn=logs.append), 1000
    )
    tail = result[result.index(TRUNCATION_NOTICE_MARKER) :]
    assert "{count}" not in tail
    assert "Z" not in tail
    assert all("Z" not in line and "{" not in line for line in logs)


def test_log_fn_receives_only_status_and_counters() -> None:
    blocks = [(0, "tool", "SECRET-" + "T" * 100)]
    reprune = _Reprune("", "SECRET-" + "T" * 100)
    logs: list[str] = []
    with_truncation_notice("T", blocks, reprune, _policy(log_fn=logs.append), 1000)
    assert len(logs) == 1
    assert "SECRET" not in logs[0]
    assert logs[0].startswith("truncation_notice applied count=1 ")


def test_json_escaping_size_fn_gets_safety_margin() -> None:
    def json_size(text: str) -> int:
        return len(json.dumps(text).encode("utf-8"))

    blocks = [(0, "tool", "T" * 800)]
    reprune = _Reprune("", "T" * 800)
    limit = 700
    result = with_truncation_notice(
        "T", blocks, reprune, NoticePolicy(size_fn=json_size), limit
    )
    assert TRUNCATION_NOTICE_MARKER in result
    assert json_size(result) <= limit


def test_second_reprune_pass_when_first_candidate_overflows() -> None:
    blocks = [(0, "tool", "T" * 800)]
    calls: list[int] = []

    def sloppy(budget: int) -> str:
        calls.append(budget)
        return "T" * (budget + 40 if len(calls) == 1 else budget)

    result = with_truncation_notice("T", blocks, sloppy, _policy(), 600)
    assert len(calls) == 2
    assert calls[1] < calls[0]
    assert _bytes(result) <= 600
    assert TRUNCATION_NOTICE_MARKER in result

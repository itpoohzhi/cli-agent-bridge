"""Общие фикстуры тестов фаз agentMessage Muse MSP.

Фикстуры повторяют форму реальных MSP-событий Muse 1.4.15
(.ai-team/runs/dsh-dup-c1/raw/msp-events*.jsonl): первым приходит
item kind=userMessage главного хода, agentMessage несёт messagePhase и turnId,
дельты — без turnId/kind, финалы подагентов могут не получать item/completed.
"""

from __future__ import annotations

from adapters.muse_msp import MspEvents

MAIN = "turn-main"
SUB = "turn-sub"


def parser(**limits: int) -> MspEvents:
    return MspEvents(
        reasoning_cap=limits.get("reasoning_cap", 1 << 20),
        answer_cap=limits.get("answer_cap", 1 << 20),
    )


def user_message(events: MspEvents, turn: str = MAIN) -> None:
    events.feed(
        "item/completed",
        {
            "item": {
                "itemId": "u1",
                "kind": "userMessage",
                "turnId": turn,
                "text": "Вопрос",
            }
        },
    )


def started(events: MspEvents, iid: str, turn: str, phase: str) -> None:
    events.feed(
        "item/started",
        {
            "item": {
                "itemId": iid,
                "kind": "agentMessage",
                "turnId": turn,
                "messagePhase": phase,
            }
        },
    )


def delta(events: MspEvents, iid: str, text: str) -> str:
    return events.feed("item/delta", {"itemId": iid, "field": "text", "delta": text})


def completed(events: MspEvents, iid: str, turn: str, phase: str, text: str) -> str:
    return events.feed(
        "item/completed",
        {
            "item": {
                "itemId": iid,
                "kind": "agentMessage",
                "turnId": turn,
                "messagePhase": phase,
                "text": text,
            }
        },
    )


def message(events: MspEvents, iid: str, turn: str, phase: str, text: str) -> None:
    started(events, iid, turn, phase)
    delta(events, iid, text)
    completed(events, iid, turn, phase, text)


def tool_started(events: MspEvents, iid: str, name: str, args: object = None) -> str:
    item: dict[str, object] = {"itemId": iid, "kind": "toolCall", "tool": name}
    if args is not None:
        item["args"] = args
    return events.feed("item/started", {"item": item})


def tool_completed(
    events: MspEvents,
    iid: str,
    name: str,
    args: object = None,
    status: str = "completed",
) -> str:
    item: dict[str, object] = {
        "itemId": iid,
        "kind": "toolCall",
        "tool": name,
        "status": status,
    }
    if args is not None:
        item["args"] = args
    return events.feed("item/completed", {"item": item})

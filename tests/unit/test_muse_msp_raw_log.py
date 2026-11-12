"""L1 RW-004: дословная форма сырого лога MSP 1.4.15 через MspEvents.feed.

Item-нагрузки сняты с .ai-team/runs/dsh-dup-c1/raw/msp-events-subagent.jsonl
(строки 5, 9, 12-14, 29-33, 56-60, 73): turnId/messagePhase внутри item,
hookRun с turnId=null до userMessage, дельты без kind/turnId, финал
подагента без item/completed, status строкой внутри item.
"""

from __future__ import annotations

from adapters.muse_msp import MspEvents
from tests.unit.msp_testlib import parser

_MAIN_TURN = "01a1cd20-85b9-79b3-87e0-e20b6d9e8abb"
_SUB_TURN = "01a1cd20-9aed-7f60-a9f5-80af2ba2c496"
_FINAL_TEXT = "Подагент проверил рабочий каталог и насчитал в нём 0 файлов."
_COMMENTARY_ID = "77213242-62a8-46d3-9c58-3d25c1b746f2"
_SUB_FINAL_ID = "61bb58cc-147c-4280-9e87-ea6b47a4cbff"
_MAIN_FINAL_ID = "d0e32e92-ec13-4d83-a209-45f5b28a798a"


def _item(iid: str, kind: str, turn: str | None, **extra: object) -> dict[str, object]:
    item: dict[str, object] = {
        "itemId": iid,
        "kind": kind,
        "turnId": turn,
        "revision": 1,
        "status": "inProgress",
    }
    item.update(extra)
    return {"item": item}


def _delta(iid: str, text: str) -> dict[str, object]:
    return {"itemId": iid, "field": "text", "delta": text}


def _opening_events() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "item/started",
            _item("01a1cd20-85f5-7622-846f-ed5c5c7045fa", "hookRun", None),
        ),
        (
            "item/completed",
            _item(
                "3add37f9-c269-43cb-86d9-87a474400adf",
                "userMessage",
                _MAIN_TURN,
                status="completed",
                text="Запусти одного подагента",
            ),
        ),
        (
            "item/started",
            _item(
                _COMMENTARY_ID,
                "agentMessage",
                _MAIN_TURN,
                text="",
                messagePhase="commentary",
            ),
        ),
    ]


def _commentary_and_sub_events() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "item/delta",
            _delta(_COMMENTARY_ID, "Запускаю подагента для подсчёта файлов."),
        ),
        (
            "item/completed",
            _item(
                _COMMENTARY_ID,
                "agentMessage",
                _MAIN_TURN,
                revision=2,
                status="completed",
                text="Запускаю подагента для подсчёта файлов.",
                messagePhase="commentary",
            ),
        ),
        (
            "item/started",
            _item(
                _SUB_FINAL_ID,
                "agentMessage",
                _SUB_TURN,
                text="",
                messagePhase="finalAnswer",
            ),
        ),
        ("item/delta", _delta(_SUB_FINAL_ID, "К")),
        ("item/delta", _delta(_SUB_FINAL_ID, "аталог")),
        ("item/delta", _delta(_SUB_FINAL_ID, " пуст")),
    ]


def _main_final_events() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "item/started",
            _item(
                _MAIN_FINAL_ID,
                "agentMessage",
                _MAIN_TURN,
                text="",
                messagePhase="finalAnswer",
            ),
        ),
        ("item/delta", _delta(_MAIN_FINAL_ID, _FINAL_TEXT)),
        (
            "item/completed",
            _item(
                _MAIN_FINAL_ID,
                "agentMessage",
                _MAIN_TURN,
                revision=2,
                status="completed",
                text=_FINAL_TEXT,
                messagePhase="finalAnswer",
            ),
        ),
        ("turn/completed", {"turnId": _MAIN_TURN, "terminal": "completed"}),
    ]


def _run_raw_log() -> MspEvents:
    events = parser()
    stream = _opening_events() + _commentary_and_sub_events() + _main_final_events()
    for method, params in stream:
        events.feed(method, params)
    return events


def test_verbatim_raw_log_stream() -> None:
    events = _run_raw_log()
    assert events.text == _FINAL_TEXT
    assert "Запускаю подагента для подсчёта файлов." in events.reasoning
    assert "Каталог пуст" in events.reasoning

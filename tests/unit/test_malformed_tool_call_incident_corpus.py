"""Регрессионный корпус malformed tool_call (incident 5): resumed-эхо и одиночная ';'.

Каждая фикстура прогоняется через боевой ``StreamNormalizer(strict_live=True)`` с
матрицей F-FSM-I2: whole / 1-byte / 7-byte / 50 фиксированных seeds + явные разрезы
внутри OPEN, ``};`` + CLOSE, JSON-escape и многобайтового UTF-8 кириллицы.
Семантический кортеж обязан совпадать на всех разрезах.
"""

from __future__ import annotations

import codecs
import json
import random
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from core import resumed_tools_policy
from core.resumed_tools_policy import build_compact_tools_reminder
from core.tool_emulation import LiveParserError, StreamNormalizer
from core.tool_mode import NormalizerSinks, ToolMode, ToollessTagPolicy, build_mode_spec
from core.tool_post_call_policy import PostCallPolicy
from scripts import qa_incident_cases

OPEN = "<tool_" + "call>"
CLOSE = "</tool_" + "call>"
_CUT_MARKERS = (OPEN, "};", CLOSE, "\\n", "Привет")


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    raw: str
    repair: bool = True
    cutoff: bool = False
    calls: int = 0
    error: str = ""
    suppressed: bool = False
    tail: tuple[str, ...] = field(default=())


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _call(name: str, args: str) -> str:
    return OPEN + '{"name":"' + name + '","arguments":' + args + "}" + CLOSE


def _raw_call(body: str) -> str:
    return OPEN + body + CLOSE


_BASH = _call("bash", '{"command":"ls"}')
_READ = _call("read", '{"path":"a.txt"}')
_ECHO = build_compact_tools_reminder(["bash", "read"])
_OLD_ECHO = OPEN + '{"name":"<tool_name>","arguments":{<json>}}' + CLOSE
_SEMI_READ = _raw_call('{"name":"read","arguments":{"path":"c.txt"}};')
_RU_ARGS = '{"command":"echo Привет\\nмир \\"ё\\""}'
_ERR_MAL = "malformed tool_call block"
_ERR_OPEN = "unclosed tool_call block"
_BAD = (
    '{"name":"bash","arguments":{"c":"a\\qb"}};',
    '{"name":"bash","arguments":{"c":"a",}};',
    '{"name":"bash","arguments":{"c":"a"}}};',
    '{"a":1}";',
    '{"a":1};"',
)

CASES: tuple[Case, ...] = (
    Case("echo_new_reminder_safe", _BASH + "\n" + _ECHO, calls=1),
    Case("echo_old_placeholder_fails", _BASH + "\n" + _OLD_ECHO, calls=1, error=_ERR_MAL),
    Case("trailing_semicolon_repaired", _BASH + _READ + _SEMI_READ, calls=3),
    Case("trailing_semicolon_repair_off", _BASH + _READ + _SEMI_READ, repair=False, calls=2, error=_ERR_MAL),
    Case("orphan_close_v1", _BASH + CLOSE, cutoff=True, calls=1, suppressed=True),
    Case("two_valid_sequential", _BASH + _READ, calls=2),
    Case("valid_valid_trailing_text", _BASH + _READ + "\nготово", calls=2),
    Case("bare_open_after_valid", _BASH + OPEN + '{"name":"bash"', calls=1, error=_ERR_OPEN),
    Case("double_semicolon", _raw_call('{"name":"read","arguments":{"path":"a"}};;'), error=_ERR_MAL),
    Case("semicolon_multibyte_utf8", _raw_call('{"name":"bash","arguments":' + _RU_ARGS + "};"), calls=1),
)
_BAD_CASES = tuple(Case(f"semicolon_corruption_{i}", _raw_call(b), error="LiveParserError") for i, b in enumerate(_BAD))


def _random_slices(data: bytes, cuts: int, seed: int) -> list[bytes]:
    rng = random.Random(seed)
    points = sorted(rng.sample(range(1, len(data)), min(cuts, len(data) - 1)))
    bounds = [0, *points, len(data)]
    return [data[a:b] for a, b in zip(bounds, bounds[1:])]


def _marker_cuts(raw: str, data: bytes) -> list[tuple[str, list[bytes]]]:
    out: list[tuple[str, list[bytes]]] = []
    for marker in _CUT_MARKERS:
        start = raw.find(marker)
        while start != -1:
            lo = len(raw[:start].encode())
            hi = lo + len(marker.encode())
            out += [(f"{marker[:6]}@{lo}+{c - lo}", [data[:c], data[c:]]) for c in range(lo, hi + 1)]
            start = raw.find(marker, start + 1)
    return out


def _variants(raw: str) -> list[tuple[str, list[bytes]]]:
    data = raw.encode("utf-8")
    out = [("whole", [data]), ("1B", [bytes([b]) for b in data])]
    out.append(("7B", [data[i : i + 7] for i in range(0, len(data), 7)]))
    out += [(f"rand_{s}", _random_slices(data, 5 + s % 20, s)) for s in range(50)]
    return out + _marker_cuts(raw, data)


def _run(case: Case, chunks: list[bytes]) -> tuple[tuple[Any, ...], dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    reasoning: list[str] = []
    sinks = NormalizerSinks(lambda _t: None, reasoning.append, calls.append)
    norm = StreamNormalizer.for_mode(build_mode_spec(ToolMode.EMULATE, ToollessTagPolicy.ERROR), sinks, strict_live=True)
    norm.configure_post_call_policy(PostCallPolicy(cutoff_enabled=case.cutoff, json_repair_enabled=case.repair))
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    error = ""
    try:
        for chunk in chunks:
            norm.feed_text(decoder.decode(chunk, final=False))
        norm.feed_text(decoder.decode(b"", final=True))
        norm.finish()
    except LiveParserError as exc:
        error = type(exc).__name__
        error += ":" + str(exc).split(" raw=")[0]
    state = str(getattr(norm, "_post_call_state", ""))
    sem = (tuple((c["name"], canonical_json(c["arguments"])) for c in calls), error, state)
    return sem, {"reasoning_chars": sum(map(len, reasoning)), "suppressed": norm.post_call_suppressed}


@pytest.mark.parametrize("case", [*CASES, *_BAD_CASES], ids=lambda c: c.name)
def test_incident_corpus_split_invariant(case: Case) -> None:
    baseline: tuple[Any, ...] | None = None
    for label, chunks in _variants(case.raw):
        sem, aux = _run(case, chunks)
        baseline = baseline or sem
        assert sem == baseline, f"{case.name}: semantic drift on {label}"
        assert len(sem[0]) == case.calls, f"{case.name}/{label}: calls={len(sem[0])}"
        assert (sem[1] == "") == (case.error == ""), f"{case.name}/{label}: error={sem[1]!r}"
        assert case.error in sem[1], f"{case.name}/{label}: error={sem[1]!r}"
        assert aux["suppressed"] is case.suppressed, f"{case.name}/{label}: suppressed"


def test_old_placeholder_text_is_gone_from_reminder() -> None:
    assert OPEN not in _ECHO and CLOSE not in _ECHO and "<json>" not in _ECHO
    assert "<tool_name>" not in _ECHO


def test_semicolon_multibyte_arguments_preserved() -> None:
    (sem, _aux) = _run(CASES[-1], [CASES[-1].raw.encode("utf-8")])
    assert sem[0] == (("bash", canonical_json({"command": 'echo Привет\nмир "ё"'})),)
    assert sem[1] == ""


def test_incident_5_qa_case_all_checks_pass_and_detect_regressions(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = {
        "incident_5_resumed_reminder_echo_safe",
        "incident_5_single_semicolon_recovered",
        "incident_5_double_semicolon_fail_closed",
    }
    checks = qa_incident_cases._check_incident_5_resumed_and_semicolon(7)  # pyright: ignore[reportPrivateUsage]
    assert set(checks) == keys and len(checks) == 3
    assert all(value is True for value in checks.values())
    monkeypatch.setattr(resumed_tools_policy, "build_compact_tools_reminder", lambda *_a, **_k: "use {<json>}")
    old = qa_incident_cases._check_incident_5_resumed_and_semicolon(7)  # pyright: ignore[reportPrivateUsage]
    assert old["incident_5_resumed_reminder_echo_safe"] is False
    monkeypatch.undo()
    stub = SimpleNamespace(tool_calls=[])
    monkeypatch.setattr(qa_incident_cases, "_parse_with_repair", lambda *_a, **_k: stub)
    broken = qa_incident_cases._check_incident_5_resumed_and_semicolon(7)  # pyright: ignore[reportPrivateUsage]
    assert broken["incident_5_single_semicolon_recovered"] is False
    assert broken["incident_5_double_semicolon_fail_closed"] is False

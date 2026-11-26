"""Wave 1 contract tests for `core.route_cb_decisions` (pure Zero-I/O FSM, REQ-001)."""

from __future__ import annotations

import ast
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.route_cb_decisions import (  # noqa: E402
    ALLOWED_EVENT_KINDS,
    ALLOWED_STATES,
    CBDecisionEffect,
    CBDecisionInput,
    CBDecisionState,
    RouteCBEvent,
    _safe,
    format_cb_event,
    sanitize_field,
    should_suppress_single_route,
    transition,
)

MODULE_PATH = ROOT / "core" / "route_cb_decisions.py"
FORBIDDEN_IMPORTS = frozenset(
    {
        "os",
        "time",
        "logging",
        "threading",
        "subprocess",
        "server",
        "core.passthrough_facade",
    }
)


def _inp(kind: str, **kw: object) -> CBDecisionInput:
    base: dict[str, object] = {
        "kind": kind,
        "provider": "codex",
        "model": "gpt-6.1-sol",
        "backend": "agy",
    }
    base.update(kw)
    return CBDecisionInput(**base)  # type: ignore[arg-type]


def _ev(**kw: object) -> RouteCBEvent:
    base: dict[str, object] = {
        "event": "open",
        "provider": "codex",
        "model": "gpt-6.1-sol",
        "backend": "agy",
        "state": "open",
        "failures": 3,
        "retry_after_s": 90,
        "route_count": 2,
        "cb_seq": 7,
    }
    base.update(kw)
    return RouteCBEvent(**base)  # type: ignore[arg-type]


# --- structural Zero-I/O / limits gate -------------------------------------------------


def test_module_zero_io_and_size_limits() -> None:
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 220
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in FORBIDDEN_IMPORTS
                assert alias.name.split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod not in FORBIDDEN_IMPORTS
            assert mod.split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, ast.FunctionDef):
            assert node.end_lineno is not None
            assert node.end_lineno - node.lineno + 1 <= 40, node.name
            n_args = (
                len(node.args.args)
                + len(node.args.posonlyargs)
                + len(node.args.kwonlyargs)
            )
            assert n_args <= 5, node.name


def test_all_dataclasses_frozen_and_slotted() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert {c.name for c in classes} >= {
        "RouteCBEvent",
        "CBDecisionState",
        "CBDecisionInput",
        "CBDecisionEffect",
    }
    for cls in classes:
        for dec in cls.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Name)
                and dec.func.id == "dataclass"
            ):
                kw = {k.arg: k.value for k in dec.keywords}
                assert (
                    isinstance(kw.get("frozen"), ast.Constant)
                    and kw["frozen"].value is True
                ), cls.name
                assert (
                    isinstance(kw.get("slots"), ast.Constant)
                    and kw["slots"].value is True
                ), cls.name


def test_constants_contract() -> None:
    assert ALLOWED_EVENT_KINDS == frozenset(
        {"open", "half_open_probe", "close", "blocked", "single_route_protection"}
    )
    assert ALLOWED_STATES == frozenset({"closed", "open", "half_open", "protected"})
    assert _safe is sanitize_field


# --- sanitize_field: secret canaries ----------------------------------------------------


@pytest.mark.parametrize(
    "canary",
    [
        "sk-CANARY",
        "route/sk-CANARY",
        "ghp_123456789012345678901234567890123456",
        "Bearer CANARY",
        "user:pass@host",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.s1g",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "a" * 33,
        "a b",
        "a\nb",
        "a\tb",
        "a\rb",
        " leading",
        "trailing ",
        "",
        "UPPER",
        "MixedCase",
        "a@b",
        "a:b",
        "a/b",
        "a\\b",
        "-lead",
        ".lead",
        "_lead",
        "sk-live-abc123",
        "gho_abc123",
        "github_pat_abc",
        "xoxb-abc",
        "xoxp-abc",
        "my-token1",
        "secret123",
        "password1",
        "apikey123",
        "api_key1",
        "bearer123",
    ],
)
def test_sanitize_field_rejects_canaries(canary: str) -> None:
    assert sanitize_field(canary) == "?"
    assert _safe(canary) == "?"


@pytest.mark.parametrize(
    "value",
    [None, 0, 123, -1, 1.5, True, False, b"codex", ["codex"], {"a": 1}, object()],
)
def test_sanitize_field_rejects_non_strings(value: object) -> None:
    assert sanitize_field(value) == "?"
    assert sanitize_field(value, frozenset({"codex"})) == "?"


@pytest.mark.parametrize(
    "legit",
    [
        "codex",
        "gpt-6.1-sol",
        "claude-sonnet-5-5",
        "dashscope-intl",
        "agy",
        "a",
        "z9",
        "a1b2c3d4e5f6",
        "a" * 32,
        "route_1",
        "model.v2",
    ],
)
def test_sanitize_field_passes_legit_ids(legit: str) -> None:
    assert sanitize_field(legit) == legit


def test_sanitize_field_allowed_mode_strict_membership() -> None:
    allowed = frozenset({"codex", "gpt-6.1-sol"})
    assert sanitize_field("codex", allowed) == "codex"
    assert sanitize_field("gpt-6.1-sol", allowed) == "gpt-6.1-sol"
    assert sanitize_field("a1b2c3d4e5f6", allowed) == "?"
    assert sanitize_field("agy", allowed) == "?"
    assert sanitize_field("", allowed) == "?"
    assert sanitize_field("codex", frozenset()) == "?"


def test_sanitize_field_allowed_mode_still_cuts_secrets_and_overlong() -> None:
    assert sanitize_field("sk-canary", frozenset({"sk-canary"})) == "?"
    assert sanitize_field("a" * 33, frozenset({"a" * 33})) == "?"
    assert sanitize_field("a" * 32, frozenset({"a" * 32})) == "a" * 32
    assert sanitize_field("Codex", frozenset({"Codex"})) == "Codex"


# --- format_cb_event ---------------------------------------------------------------------


def test_format_cb_event_exact_shape() -> None:
    line = format_cb_event(_ev())
    assert line == (
        "route_cb event=open provider=codex model=gpt-6.1-sol backend=agy state=open"
        " failures=3 retry_after_s=90 route_count=2 cb_seq=7"
    )


@pytest.mark.parametrize("bad", ["evil", "", "OPEN", "open ", "sk-CANARY"])
def test_format_cb_event_unknown_event_kind_masked(bad: str) -> None:
    assert f"event={bad} " not in format_cb_event(_ev(event=bad))
    assert format_cb_event(_ev(event=bad)).startswith("route_cb event=? ")


@pytest.mark.parametrize("bad", ["weird", "", "OPEN", "protected "])
def test_format_cb_event_unknown_state_masked(bad: str) -> None:
    assert format_cb_event(_ev(state=bad)).find(" state=? ") != -1


def test_format_cb_event_sanitizes_identity_fields() -> None:
    line = format_cb_event(
        _ev(provider="sk-CANARY", model="user:pass@host", backend="a" * 33)
    )
    assert " provider=? " in line
    assert " model=? " in line
    assert " backend=? " in line
    assert "sk-CANARY" not in line


def test_format_cb_event_allowed_mode() -> None:
    line = format_cb_event(_ev(provider="codex", model="other"), frozenset({"codex"}))
    assert " provider=codex " in line
    assert " model=? " in line


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("failures", -5, 0),
        ("failures", 10**9, 9999),
        ("retry_after_s", -1, 0),
        ("retry_after_s", 10000, 9999),
        ("route_count", -3, 0),
        ("route_count", 10000, 9999),
        ("cb_seq", -3, 0),
        ("cb_seq", 10**12, 9999999999),
    ],
)
def test_format_cb_event_clamps_ints(field: str, raw: int, expected: int) -> None:
    line = format_cb_event(_ev(**{field: raw}))
    assert f" {field}={expected} " in line or line.endswith(f" {field}={expected}")


def test_format_cb_event_worst_case_byte_bound_and_tail_intact() -> None:
    ev = _ev(
        event="single_route_protection",
        provider="a" * 32,
        model="b" * 32,
        backend="c" * 32,
        state="half_open",
        failures=9999,
        retry_after_s=9999,
        route_count=9999,
        cb_seq=9_999_999_999,
    )
    line = format_cb_event(ev)
    expected = (
        "route_cb event=single_route_protection provider={} model={} backend={} state=half_open"
        " failures=9999 retry_after_s=9999 route_count=9999 cb_seq=9999999999"
    ).format("a" * 32, "b" * 32, "c" * 32)
    assert line == expected
    assert len(line.encode("utf-8")) <= 256
    assert line.endswith("cb_seq=9999999999")


# --- should_suppress_single_route: 429/401/402/403 carve-out ------------------------------


@pytest.mark.parametrize(
    ("protect", "route_count", "status", "is_auth", "expected"),
    [
        (True, 1, 429, False, False),
        (True, 1, 500, False, True),
        (True, 2, 500, False, False),
        (True, 1, 401, False, False),
        (True, 1, 402, False, False),
        (True, 1, 403, False, False),
        (False, 1, 500, False, False),
        (True, 0, 500, False, False),
        (True, 1, None, False, True),
        (True, 1, 200, False, True),
        (True, 1, 500, True, False),
        (True, 1, 429, True, False),
    ],
)
def test_should_suppress_single_route_matrix(
    protect: bool, route_count: int, status: int | None, is_auth: bool, expected: bool
) -> None:
    assert (
        should_suppress_single_route(protect, route_count, status, is_auth) is expected
    )


# --- transition: exhaustive State x Event -------------------------------------------------


@pytest.mark.parametrize(
    (
        "provider_open",
        "tuple_open",
        "protect",
        "route_count",
        "status",
        "is_auth",
        "action",
        "event",
        "state",
    ),
    [
        (True, True, True, 1, 500, False, "deny", "blocked", "open"),
        (True, False, False, 0, None, False, "deny", "blocked", "open"),
        (
            False,
            True,
            True,
            1,
            500,
            False,
            "allow",
            "single_route_protection",
            "protected",
        ),
        (
            False,
            True,
            True,
            1,
            None,
            False,
            "allow",
            "single_route_protection",
            "protected",
        ),
        (False, True, True, 1, 429, False, "deny", "blocked", "open"),
        (False, True, True, 1, 401, False, "deny", "blocked", "open"),
        (False, True, True, 1, 402, False, "deny", "blocked", "open"),
        (False, True, True, 1, 403, False, "deny", "blocked", "open"),
        (False, True, True, 2, 500, False, "deny", "blocked", "open"),
        (False, True, False, 1, 500, False, "deny", "blocked", "open"),
        (False, True, True, 1, 500, True, "deny", "blocked", "open"),
        (False, False, True, 1, 500, False, "deny", "blocked", "open"),
    ],
)
def test_transition_acquire_blocked_matrix(
    provider_open: bool,
    tuple_open: bool,
    protect: bool,
    route_count: int,
    status: int | None,
    is_auth: bool,
    action: str,
    event: str,
    state: str,
) -> None:
    inp = _inp(
        "acquire_blocked",
        provider_open=provider_open,
        tuple_open=tuple_open,
        single_route_protect=protect,
        route_count=route_count,
        status=status,
        is_auth=is_auth,
        failures=4,
        retry_after_s=77,
    )
    new_state, effects = transition(CBDecisionState(cb_seq=7), inp)
    assert len(effects) == 1
    assert effects[0].action == action
    ev = effects[0].event
    assert ev is not None
    assert ev.event == event
    assert ev.state == state
    assert ev.cb_seq == 8
    assert new_state == CBDecisionState(cb_seq=8)
    assert ev.provider == "codex" and ev.model == "gpt-6.1-sol" and ev.backend == "agy"
    assert ev.failures == 4 and ev.route_count == route_count
    assert ev.retry_after_s == (0 if event == "single_route_protection" else 77)


def test_transition_acquire_probe() -> None:
    new_state, effects = transition(
        CBDecisionState(cb_seq=0), _inp("acquire_probe", failures=2, retry_after_s=30)
    )
    assert new_state == CBDecisionState(cb_seq=1)
    assert effects == (
        CBDecisionEffect(
            "allow",
            RouteCBEvent(
                "half_open_probe",
                "codex",
                "gpt-6.1-sol",
                "agy",
                "half_open",
                2,
                30,
                0,
                1,
            ),
        ),
    )


@pytest.mark.parametrize(
    ("is_auth", "status", "opened_now", "protect", "route_count", "action", "event"),
    [
        (True, None, True, False, 0, "auth_delegate", "open"),
        (True, None, False, False, 0, "auth_delegate", None),
        (True, 500, True, True, 1, "auth_delegate", "open"),
        (False, 401, True, False, 0, "auth_delegate", "open"),
        (False, 402, False, False, 0, "auth_delegate", None),
        (False, 403, True, True, 1, "auth_delegate", "open"),
        (False, 429, True, False, 0, "bump_tuple_fail", "open"),
        (False, 429, True, True, 1, "bump_tuple_fail", "open"),
        (
            False,
            500,
            True,
            True,
            1,
            "suppress_tuple_cooldown",
            "single_route_protection",
        ),
        (
            False,
            500,
            False,
            True,
            1,
            "suppress_tuple_cooldown",
            "single_route_protection",
        ),
        (
            False,
            None,
            True,
            True,
            1,
            "suppress_tuple_cooldown",
            "single_route_protection",
        ),
        (False, 500, True, False, 0, "bump_tuple_fail", "open"),
        (False, 500, False, False, 0, "bump_tuple_fail", None),
        (False, 500, True, True, 2, "bump_tuple_fail", "open"),
        (False, None, True, False, 0, "bump_tuple_fail", "open"),
    ],
)
def test_transition_record_failure_matrix(
    is_auth: bool,
    status: int | None,
    opened_now: bool,
    protect: bool,
    route_count: int,
    action: str,
    event: str | None,
) -> None:
    inp = _inp(
        "record_failure",
        is_auth=is_auth,
        status=status,
        opened_now=opened_now,
        single_route_protect=protect,
        route_count=route_count,
        failures=5,
        retry_after_s=90,
    )
    new_state, effects = transition(CBDecisionState(cb_seq=11), inp)
    assert len(effects) == 1
    assert effects[0].action == action
    ev = effects[0].event
    if event is None:
        assert ev is None
        assert new_state == CBDecisionState(cb_seq=11)
    else:
        assert ev is not None
        assert ev.event == event
        assert ev.cb_seq == 12
        assert new_state == CBDecisionState(cb_seq=12)
        assert ev.state == (
            "protected" if event == "single_route_protection" else "open"
        )
        assert ev.retry_after_s == (0 if event == "single_route_protection" else 90)
        assert ev.failures == 5 and ev.route_count == route_count


@pytest.mark.parametrize("was_open", [True, False])
def test_transition_record_success(was_open: bool) -> None:
    inp = _inp(
        "record_success", was_open=was_open, failures=9, retry_after_s=45, route_count=3
    )
    new_state, effects = transition(CBDecisionState(cb_seq=4), inp)
    assert len(effects) == 1
    assert effects[0].action == "noop"
    if was_open:
        ev = effects[0].event
        assert ev is not None
        assert ev.event == "close" and ev.state == "closed"
        assert ev.failures == 0 and ev.retry_after_s == 0 and ev.route_count == 3
        assert ev.cb_seq == 5
        assert new_state == CBDecisionState(cb_seq=5)
    else:
        assert effects[0].event is None
        assert new_state == CBDecisionState(cb_seq=4)


@pytest.mark.parametrize("kind", ["bogus", "", "OPEN", "acquire", "record", "close"])
def test_transition_unknown_kind_raises(kind: str) -> None:
    with pytest.raises(ValueError, match=f"unknown decision kind: {kind}"):
        transition(CBDecisionState(), _inp(kind))


def test_transition_cb_seq_monotonic_across_chain() -> None:
    state = CBDecisionState(cb_seq=0)
    steps = [
        _inp("acquire_blocked", tuple_open=True),
        _inp("acquire_probe"),
        _inp("record_failure", opened_now=True),
        _inp("record_failure", opened_now=False),
        _inp("record_success", was_open=False),
        _inp("record_success", was_open=True),
    ]
    expected_seq = [1, 2, 3, 3, 3, 4]
    for inp, want in zip(steps, expected_seq, strict=True):
        state, effects = transition(state, inp)
        assert state.cb_seq == want
        for eff in effects:
            if eff.event is not None:
                assert eff.event.cb_seq == want


def test_transition_deterministic_and_pure() -> None:
    state = CBDecisionState(cb_seq=3)
    inp = _inp("record_failure", opened_now=True, failures=2)
    first = transition(state, inp)
    second = transition(state, inp)
    assert first == second
    assert state == CBDecisionState(cb_seq=3)


def test_records_are_frozen() -> None:
    state = CBDecisionState()
    inp = _inp("acquire_probe")
    _, effects = transition(state, inp)
    ev = effects[0].event
    assert ev is not None
    with pytest.raises(FrozenInstanceError):
        state.cb_seq = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        inp.kind = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ev.event = "x"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        effects[0].action = "x"  # type: ignore[misc]

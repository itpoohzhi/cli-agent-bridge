"""System-prefix session affinity anchor (BRIDGE_SESSION_AFFINITY_SYSTEM_ANCHOR_ENABLED)."""

import itertools
import json
import uuid

import pytest

import core.session_affinity as sa
from core.session_affinity_anchor import (
    FLAG_SYSTEM_ANCHOR,
    MIN_SYSTEM_ANCHOR_CHARS,
    is_system_anchor_enabled,
)

LONG_SYS = "You are a helpful assistant. " * 60  # > 1024 chars
SHORT_SYS = "Be brief."
_CFG_SEQ = itertools.count()


@pytest.fixture
def flags(tmp_path, monkeypatch):
    monkeypatch.setattr(sa, "_get_salt", lambda: b"k" * 32)

    def _set(*, stable=True, anchor=False):
        path = tmp_path / f"cfg_{next(_CFG_SEQ)}.json"
        path.write_text(
            json.dumps(
                {
                    "BRIDGE_STABLE_SESSION_AFFINITY_ENABLED": stable,
                    FLAG_SYSTEM_ANCHOR: anchor,
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
        monkeypatch.setenv("BRIDGE_STABLE_SESSION_AFFINITY_ENABLED", str(stable).lower())
        monkeypatch.setenv(FLAG_SYSTEM_ANCHOR, str(anchor).lower())

    return _set


def _affinity(messages, *, model="deepseek-v4.1-flash", headers=None, **extra):
    data = {"model": model, "messages": messages, **extra}
    raw = json.dumps(data).encode("utf-8")
    return sa.session_affinity(raw, headers or {}, "opencode-go")


def _single(system, user):
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def test_flag_default_off(flags):
    flags(stable=True, anchor=False)
    assert is_system_anchor_enabled() is False
    assert MIN_SYSTEM_ANCHOR_CHARS == 1024


def test_legacy_parity_flag_off_different_uuids(flags):
    flags(stable=True, anchor=False)
    a = _affinity(_single(LONG_SYS, "Question A?"))
    b = _affinity(_single(LONG_SYS, "Question B?"))
    assert a != b


def test_flag_on_same_long_system_same_uuid5(flags):
    flags(stable=True, anchor=True)
    a = _affinity(_single(LONG_SYS, "Question A?"))
    b = _affinity(_single(LONG_SYS, "Question B?"))
    assert a == b
    assert uuid.UUID(a).version == 5


def test_multi_turn_still_includes_first_user(flags):
    flags(stable=True, anchor=True)
    turn2 = [
        {"role": "system", "content": LONG_SYS},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
    ]
    other = [
        {"role": "system", "content": LONG_SYS},
        {"role": "user", "content": "uA"},
        {"role": "assistant", "content": "aA"},
        {"role": "user", "content": "uB"},
    ]
    turn3 = turn2 + [
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
    ]
    assert _affinity(turn2) != _affinity(other)
    assert _affinity(turn2) == _affinity(turn3)


def test_short_system_flag_on_still_differs(flags):
    flags(stable=True, anchor=True)
    assert len(SHORT_SYS) < MIN_SYSTEM_ANCHOR_CHARS
    a = _affinity(_single(SHORT_SYS, "Question A?"))
    b = _affinity(_single(SHORT_SYS, "Question B?"))
    assert a != b


@pytest.mark.parametrize("anchor", [False, True])
def test_explicit_keys_take_precedence(flags, anchor):
    flags(stable=True, anchor=anchor)
    a = _affinity(_single(LONG_SYS, "A?"), prompt_cache_key="pck-1")
    b = _affinity(_single(LONG_SYS, "B?"), prompt_cache_key="pck-1")
    c = _affinity(_single(LONG_SYS, "A?"), prompt_cache_key="pck-2")
    assert a == b != c
    s1 = _affinity(_single(LONG_SYS, "A?"), session_id="sess-1")
    s2 = _affinity(_single(LONG_SYS, "B?"), session_id="sess-1")
    assert s1 == s2 != a
    h = {"x-opencode-session": "header-sess"}
    h1 = _affinity(_single(LONG_SYS, "A?"), headers=h)
    h2 = _affinity(_single(LONG_SYS, "B?"), headers=h)
    assert h1 == h2 != a


def test_cross_api_key_isolation(flags):
    flags(stable=True, anchor=True)
    msgs = _single(LONG_SYS, "Same question?")
    a = _affinity(msgs, headers={"authorization": "Bearer key-one"})
    b = _affinity(msgs, headers={"authorization": "Bearer key-two"})
    assert a != b


def test_cross_model_isolation(flags):
    flags(stable=True, anchor=True)
    msgs = _single(LONG_SYS, "Same question?")
    a = _affinity(msgs, model="deepseek-v4.1-flash")
    b = _affinity(msgs, model="deepseek-v4.1-pro")
    assert a != b


def test_block_list_system_content_triggers_anchor(flags):
    flags(stable=True, anchor=True)
    blocks = [
        {"type": "text", "text": LONG_SYS, "cache_control": {"type": "ephemeral"}}
    ]
    a = _affinity([{"role": "system", "content": blocks}, {"role": "user", "content": "A?"}])
    b = _affinity([{"role": "system", "content": blocks}, {"role": "user", "content": "B?"}])
    assert a == b
    assert uuid.UUID(a).version == 5


def test_exact_threshold_boundary(flags):
    """Ровно MIN_SYSTEM_ANCHOR_CHARS включает якорь (>=), на 1 символ меньше — нет."""
    flags(stable=True, anchor=True)
    exact = "x" * MIN_SYSTEM_ANCHOR_CHARS
    a = _affinity(_single(exact, "A?"))
    b = _affinity(_single(exact, "B?"))
    assert a == b
    assert uuid.UUID(a).version == 5
    below = "x" * (MIN_SYSTEM_ANCHOR_CHARS - 1)
    c = _affinity(_single(below, "A?"))
    d = _affinity(_single(below, "B?"))
    assert c != d


def test_top_level_system_string_triggers_anchor(flags):
    flags(stable=True, anchor=True)
    a = _affinity([{"role": "user", "content": "A?"}], system=LONG_SYS)
    b = _affinity([{"role": "user", "content": "B?"}], system=LONG_SYS)
    assert a == b


def test_stable_flag_off_gives_random_uuid4(flags):
    flags(stable=False, anchor=True)
    a = _affinity(_single(LONG_SYS, "A?"))
    b = _affinity(_single(LONG_SYS, "A?"))
    assert a != b
    assert uuid.UUID(a).version == 4

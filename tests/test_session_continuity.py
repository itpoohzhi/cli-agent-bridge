"""L1: непрерывность чата без chat id (core/session_continuity)."""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.session_continuity import (  # noqa: E402
    ContinuityConfig,
    ContinuityIndex,
    canonical_digest,
    session_key_for,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _counter() -> Callable[[], str]:
    state = {"n": 0}

    def make() -> str:
        state["n"] += 1
        return f"c{state['n']}"

    return make


def _index(
    max_links: int = 4096,
    ttl_s: float = 1800.0,
    log_fn: Callable[[str], None] | None = None,
) -> tuple[ContinuityIndex, FakeClock]:
    clock = FakeClock()
    cfg = ContinuityConfig(max_links=max_links, ttl_s=ttl_s, log_fn=log_fn)
    return ContinuityIndex(cfg, clock, _counter()), clock


def _u(text: str) -> dict[str, object]:
    return {"role": "user", "content": text}


def _a(text: str) -> dict[str, object]:
    return {"role": "assistant", "content": text}


def _turns(n: int, tag: str = "") -> list[list[dict[str, object]]]:
    """Истории ходов 1..n: u1; u1 a1 u2; u1 a1 u2 a2 u3; ..."""
    out: list[list[dict[str, object]]] = []
    msgs: list[dict[str, object]] = []
    for i in range(1, n + 1):
        if i > 1:
            msgs.append(_a(f"{tag}a{i - 1}"))
        msgs.append(_u(f"{tag}u{i}"))
        out.append(list(msgs))
    return out


# --- canonical_digest ---------------------------------------------------


def test_digest_ignores_client_metadata_and_key_order() -> None:
    base = [{"role": "user", "content": "hi"}]
    noisy = [
        {
            "content": "hi",
            "role": "user",
            "timestamp": 123,
            "cache_control": {"type": "ephemeral"},
            "metadata": {"x": 1},
            "id": "msg-1",
        }
    ]
    assert canonical_digest(base, "s") == canonical_digest(noisy, "s")


def test_digest_ignores_cache_control_inside_content_parts() -> None:
    plain = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    noisy = [
        {
            "role": "user",
            "content": [{"text": "hi", "type": "text", "cache_control": {"type": "e"}}],
        }
    ]
    assert canonical_digest(plain) == canonical_digest(noisy)


def test_digest_is_sensitive_to_scope_and_content() -> None:
    msgs = [_u("hi")]
    assert canonical_digest(msgs, "m1\x00/a") != canonical_digest(msgs, "m2\x00/a")
    assert canonical_digest(msgs, "m1\x00/a") != canonical_digest(msgs, "m1\x00/b")
    assert canonical_digest(msgs) != canonical_digest([_u("hi!")])
    assert canonical_digest([_u("x")]) != canonical_digest([_a("x")])


def _asst_call(call_id: str, args: str) -> list[dict[str, object]]:
    call = {"id": call_id, "function": {"name": "bash", "arguments": args}}
    return [{"role": "assistant", "content": None, "tool_calls": [call]}]


def test_digest_is_sensitive_to_tool_call_id_and_arguments() -> None:
    base = canonical_digest(_asst_call("t1", '{"c":"ls"}'))
    assert base == canonical_digest(_asst_call("t1", '{"c":"ls"}'))
    assert base != canonical_digest(_asst_call("t2", '{"c":"ls"}'))
    assert base != canonical_digest(_asst_call("t1", '{"c":"pwd"}'))


def test_digest_covers_tool_result_fields() -> None:
    one = [{"role": "tool", "tool_call_id": "t1", "name": "bash", "content": "ok"}]
    two = [{"role": "tool", "tool_call_id": "t2", "name": "bash", "content": "ok"}]
    assert canonical_digest(one) != canonical_digest(two)


# --- ContinuityIndex: цепочка ------------------------------------------


def test_chain_is_stable_across_three_turns() -> None:
    idx, _ = _index()
    t1, t2, t3 = _turns(3)
    c1 = idx.resolve(t1, "s")
    assert idx.resolve(t2, "s") == c1
    assert idx.resolve(t3, "s") == c1


def test_invalid_messages_give_empty_chain() -> None:
    idx, _ = _index()
    assert idx.resolve([], "s") == ""
    assert idx.resolve(None, "s") == ""
    assert idx.resolve("text", "s") == ""
    assert idx.link_count() == 0


def test_prefix_entry_is_single_use() -> None:
    idx, _ = _index()
    t1, t2 = _turns(2)
    c1 = idx.resolve(t1, "s")
    assert idx.resolve(t2, "s") == c1
    # Повтор того же хода 2: запись префикса уже изъята — холодный chain.
    assert idx.resolve(t2, "s") != c1


def test_identical_first_requests_conflict_into_tombstone() -> None:
    idx, _ = _index()
    (a1,) = _turns(1)
    (b1,) = _turns(1)
    ca1 = idx.resolve(a1, "s")
    cb1 = idx.resolve(b1, "s")
    assert ca1 != cb1
    ca2 = idx.resolve(_turns(2)[1], "s")
    cb2 = idx.resolve(_turns(2)[1], "s")
    assert len({ca1, cb1, ca2, cb2}) == 4


def test_identical_first_requests_in_different_scopes_do_not_conflict() -> None:
    idx, _ = _index()
    t1, t2 = _turns(2)
    c_m1 = idx.resolve(t1, "m1\x00/w")
    c_m2 = idx.resolve(t1, "m2\x00/w")
    c_w2 = idx.resolve(t1, "m1\x00/other")
    assert idx.resolve(t2, "m1\x00/w") == c_m1
    assert idx.resolve(t2, "m2\x00/w") == c_m2
    assert idx.resolve(t2, "m1\x00/other") == c_w2
    assert len({c_m1, c_m2, c_w2}) == 3


def test_sequential_identical_chats_do_not_merge() -> None:
    idx, _ = _index()
    t1, t2 = _turns(2)
    idx.resolve(t1, "s")
    chain_a = idx.resolve(t2, "s")  # Ход 2 A: pop
    idx.resolve(t1, "s")  # Ход 1 B: полный дайджест хода 1 свободен снова
    chain_b = idx.resolve(t2, "s")
    assert chain_a != chain_b


# --- вытеснение и TTL --------------------------------------------------


def test_max_links_evicts_oldest() -> None:
    idx, _ = _index(max_links=2)
    chat_a, chat_b, chat_c = (_turns(2, tag=t) for t in "abc")
    ca = idx.resolve(chat_a[0], "s")
    idx.resolve(chat_b[0], "s")
    idx.resolve(chat_c[0], "s")
    assert idx.link_count() == 2
    assert idx.resolve(chat_a[1], "s") != ca  # цепочка A вытеснена
    assert idx.resolve(chat_c[1], "s") != ""


def test_ttl_expires_links() -> None:
    idx, clock = _index(ttl_s=10.0)
    t1, t2 = _turns(2)
    c1 = idx.resolve(t1, "s")
    clock.now += 10.5
    assert idx.resolve(t2, "s") != c1


def test_ttl_boundary_keeps_link() -> None:
    idx, clock = _index(ttl_s=10.0)
    t1, t2 = _turns(2)
    c1 = idx.resolve(t1, "s")
    clock.now += 10.0
    assert idx.resolve(t2, "s") == c1


def test_expired_entries_are_purged() -> None:
    idx, clock = _index(ttl_s=5.0)
    idx.resolve(_turns(1, tag="a")[0], "s")
    idx.resolve(_turns(1, tag="b")[0], "s")
    clock.now += 6.0
    idx.resolve(_turns(1, tag="c")[0], "s")
    assert idx.link_count() == 1


def test_config_clamps_invalid_values() -> None:
    cfg = ContinuityConfig(max_links=0, ttl_s=-1.0)
    assert cfg.max_links == 1
    assert cfg.ttl_s > 0


# --- логирование -------------------------------------------------------


def test_log_contains_only_status_and_counter() -> None:
    lines: list[str] = []
    idx, _ = _index(log_fn=lines.append)
    secret = "TOPSECRET-token-123"
    t1 = [_u(f"my password is {secret}")]
    idx.resolve(t1, "model\x00/home/u")
    idx.resolve([*t1, _a("reply " + secret), _u("more " + secret)], "model\x00/home/u")
    assert lines == [
        "continuity status=init links=1",
        "continuity status=hit links=1",
    ]
    joined = "\n".join(lines)
    assert secret not in joined
    assert "password" not in joined
    assert "/home/u" not in joined


# --- session_key_for ---------------------------------------------------


def _tok(chat: str) -> str:
    return hashlib.sha256(chat.encode("utf-8")).hexdigest()


_CASES: list[tuple[tuple[object, ...], tuple[str, ...]]] = [
    (("m", "/w/p", "hi", "chat-1"), (_tok("chat-1"), "m", "/w/p", "hi")),
    (("m", "/w/../w/p/", "hi", " chat-1 "), (_tok("chat-1"), "m", "/w/p", "hi")),
    (("m", "/w/p", "hi", ""), ("m", "/w/p", "hi")),
    (("m", None, "hi", "chat-1"), (_tok("chat-1"), "m", "", "hi")),
    (("m", "", "hi", "chat-1"), (_tok("chat-1"), "m", "", "hi")),
    (("m", "   ", "hi", "chat-1"), (_tok("chat-1"), "m", "", "hi")),
    (("m", None, "hi", ""), ()),
    (("m", "", "hi", ""), ()),
    (("m", "/w/p", "hi", "bad\nchat"), ()),
    (("m", "/w/p", "hi", "bad\x7fchat"), ()),
    (("m", "/w/p", "hi", "bad\ud800chat"), ()),
    (("m", "relative/p", "hi", "chat-1"), ()),
    (("m", "/w/\x00p", "hi", "chat-1"), ()),
    (("m", "/w/p\tq", "hi", "chat-1"), ()),
    (("m", "/w/\udc80", "hi", "chat-1"), ()),
    (("m", 123, "hi", "chat-1"), ()),
    (("m", "/" + "a" * 2000, "hi", "chat-1"), ()),
]


@pytest.mark.parametrize(("args", "expected"), _CASES)
def test_session_key_for_table(
    args: tuple[object, ...], expected: tuple[str, ...]
) -> None:
    model, cwd, effort, chat = args
    assert session_key_for(str(model), cwd, str(effort), str(chat)) == expected


def test_session_key_for_cwd_max_len_is_configurable() -> None:
    cwd = "/" + "a" * 100
    assert session_key_for("m", cwd, "e", "", cwd_max_len=50) == ()
    assert session_key_for("m", cwd, "e", "", cwd_max_len=200) == ("m", cwd, "e")


def test_session_key_for_non_str_chat_id_is_ignored() -> None:
    key = session_key_for("m", "/w", "e", 5)  # type: ignore[arg-type]
    assert key == ("m", "/w", "e")

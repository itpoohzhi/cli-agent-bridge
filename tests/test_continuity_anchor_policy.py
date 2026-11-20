"""Unit-тесты для core/continuity_anchor_policy.py и ContinuityIndex.register_post_turn (W5, D2)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.continuity_anchor_policy import (  # noqa: E402
    BRIDGE_CALL_ID_RE,
    PostTurnAnchorIndex,
    build_post_turn_anchor_key,
    extract_valid_bridge_call_ids,
    mint_bridge_call_id,
)
from core.session_continuity import ContinuityConfig, ContinuityIndex  # noqa: E402


def test_mint_and_extract_valid_bridge_call_ids() -> None:
    cid1 = mint_bridge_call_id()
    cid2 = mint_bridge_call_id()
    assert cid1 != cid2
    assert BRIDGE_CALL_ID_RE.fullmatch(cid1)
    assert BRIDGE_CALL_ID_RE.fullmatch(cid2)

    extracted = extract_valid_bridge_call_ids(
        [
            {"id": cid2},
            {"id": "call_1"},  # слишком короткий модельный id — отбросить
            {"id": cid1},
            {"id": cid1},  # дубликат
            {"id": "call_" + "Z" * 24},  # не hex
            "not-a-dict",
        ]
    )
    assert extracted == tuple(sorted((cid1, cid2)))
    assert extract_valid_bridge_call_ids("invalid") == ()


def test_build_post_turn_anchor_key_rejects_empty_ids() -> None:
    cid = mint_bridge_call_id()
    assert build_post_turn_anchor_key("model-a", "abc", []) is None
    assert build_post_turn_anchor_key("model-a", "abc", ["call_short"]) is None
    assert build_post_turn_anchor_key("model-a", "", [cid]) is None
    k1 = build_post_turn_anchor_key("model-a", "abc", [cid])
    k2 = build_post_turn_anchor_key("model-b", "abc", [cid])
    assert k1 is not None and k2 is not None and k1 != k2


def test_post_turn_anchor_index_ttl_lru_conflict_and_single_use() -> None:
    idx = PostTurnAnchorIndex(max_links=2, ttl_s=10.0)
    assert idx.register("k1", "c1", 100.0) == "registered"
    assert idx.register("k2", "c2", 101.0) == "registered"
    assert idx.count() == 2
    # LRU вытеснение k1 при добавлении k3
    assert idx.register("k3", "c3", 102.0) == "registered"
    assert idx.count() == 2
    assert idx.claim("k1", 103.0) == (None, "miss")
    # Одноразовый pop
    assert idx.claim("k2", 103.0) == ("c2", "hit")
    assert idx.claim("k2", 103.0) == (None, "miss")
    # Конфликт разных chain -> tombstone
    assert idx.register("k3", "c_other", 104.0) == "conflict_tombstone"
    assert idx.claim("k3", 105.0) == (None, "tombstone")
    # TTL истечение
    assert idx.register("k4", "c4", 105.0) == "registered"
    assert idx.claim("k4", 116.0) == (None, "miss")


def test_continuity_index_t1_to_t2_hot_chain() -> None:
    logs: list[str] = []
    idx = ContinuityIndex(
        config=ContinuityConfig(max_links=16, ttl_s=60.0, log_fn=logs.append),
        clock=lambda: 100.0,
    )
    t1_msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "read 1"}]
    chain_t1 = idx.resolve(t1_msgs, "gemini-4-neon-high")
    emitted_id = mint_bridge_call_id()
    assert idx.register_post_turn(t1_msgs, "gemini-4-neon-high", chain_t1, []) is False
    assert idx.register_post_turn(t1_msgs, "gemini-4-neon-high", chain_t1, ["call_1"]) is False
    assert idx.register_post_turn(t1_msgs, "gemini-4-neon-high", chain_t1, [emitted_id]) is True
    t2_msgs = [
        *t1_msgs,
        {
            "role": "assistant",
            "content": "reformatted",
            "tool_calls": [{"id": emitted_id, "type": "function", "function": {"name": "r", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": emitted_id, "content": "CHUNK_1"},
    ]
    assert idx.resolve(t2_msgs, "gemini-4-neon-high") == chain_t1
    assert any("status=post_hit" in line for line in logs)
    assert idx.resolve(t2_msgs, "gemini-4-neon-high") != chain_t1


def test_continuity_index_post_turn_kill_switch() -> None:
    enabled = [False]
    idx = ContinuityIndex(
        config=ContinuityConfig(max_links=16, ttl_s=60.0, post_turn_anchor_enabled=lambda: enabled[0]),
        clock=lambda: 100.0,
    )
    t1_msgs = [{"role": "user", "content": "hi"}]
    c_new = idx.resolve(t1_msgs, "gemini-4-neon-high")
    cid = mint_bridge_call_id()
    assert idx.register_post_turn(t1_msgs, "gemini-4-neon-high", c_new, [cid]) is False
    enabled[0] = True
    assert idx.register_post_turn(t1_msgs, "gemini-4-neon-high", c_new, [cid], enabled=False) is False

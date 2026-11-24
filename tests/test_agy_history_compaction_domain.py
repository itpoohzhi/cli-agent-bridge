"""VER-002: чистые unit-тесты домена компакции истории (W1, AD-001).

Без моков транспорта, сети и ``server.py``: канарейка первого user-сообщения,
атомарность tool-пар, жёсткий предел байт, детерминизм и стабильность
``prompt_prefix_sha256``, краевые случаи и AST-чистота домена.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = _ROOT / "bridges" / "agy-bridge"
sys.path.insert(0, str(BRIDGE_DIR))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agy_runtime.history_compaction_domain import (  # noqa: E402
    DEFAULT_MIDDLE_PRUNED_MARKER,
    CompactionConfig,
    PromptBlock,
    anchor_prefix_sha256,
    compact_prompt_blocks,
    json_text_bytes,
    middle_prune_text,
)
import agy_runtime.history_compaction_domain as compaction_domain  # noqa: E402

_CANARY = "CANARY_FACT_ALPHA_7391"
_CODENAME = "LARCH-7391"
_PAIR_ID = "call_pair_42"
_LIMIT = 98304
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _block(index: int, role: str, body: str) -> PromptBlock:
    return PromptBlock(index=index, role=role, rendered=f"### {index}. {role}\n{body}")


def _tool_turn(start: int, turn: int, body_chars: int = 4200) -> list[PromptBlock]:
    call_id = "call_%02d" % turn
    return [
        _block(start, "user", f"step {turn}: read chunk {turn}"),
        _block(start + 1, "assistant", f"[tool call {call_id}] read_chunk({turn})"),
        _block(
            start + 2,
            "tool",
            f"[tool result {call_id}] result-{turn:02d}-" + "x" * body_chars,
        ),
    ]


def _canary_blocks(turns: int = 32) -> list[PromptBlock]:
    blocks = [
        _block(0, "system", "You are a test assistant. Follow the conversation."),
        _block(
            1, "user", f"Remember this fact: {_CANARY} project codename is {_CODENAME}."
        ),
    ]
    for turn in range(turns):
        blocks.extend(_tool_turn(2 + turn * 3, turn))
    blocks.append(_block(2 + turns * 3, "user", "What is the project codename?"))
    return blocks


def _cfg(limit: int = _LIMIT) -> CompactionConfig:
    return CompactionConfig(limit_bytes=limit)


def test_canary_first_user_preserved_over_32_turns() -> None:
    result = compact_prompt_blocks(_canary_blocks(), _cfg())
    assert result.prompt_bytes <= _LIMIT
    assert json_text_bytes(result.prompt) == result.prompt_bytes
    assert _CANARY in result.prompt
    assert _CODENAME in result.prompt
    assert "What is the project codename?" in result.prompt
    assert result.digested_count > 0
    assert result.dropped_count == 0


_CANARY_LINE2 = "CANARY_LINE_TWO_7391 survives verbatim only in anchor"


def _delayed_user_blocks(turns: int) -> list[PromptBlock]:
    blocks = [
        _block(0, "system", "You are a test assistant."),
        _block(1, "assistant", "[tool call boot_0] warm_up()"),
        _block(2, "tool", "[tool result boot_0] ready"),
        _block(3, "user", f"Remember:\n{_CANARY} is {_CODENAME}\n{_CANARY_LINE2}"),
    ]
    for turn in range(turns):
        blocks.extend(_tool_turn(4 + turn * 3, turn))
    blocks.append(_block(4 + turns * 3, "user", "What is the project codename?"))
    return blocks


def test_anchor_includes_delayed_first_user_canary() -> None:
    result = compact_prompt_blocks(_delayed_user_blocks(32), _cfg())
    assert result.prompt_bytes <= _LIMIT
    assert _CANARY in result.prompt
    assert _CANARY_LINE2 in result.prompt
    assert "What is the project codename?" in result.prompt


def test_anchor_hash_includes_delayed_first_user_group() -> None:
    base = _delayed_user_blocks(8)
    grown = _delayed_user_blocks(32)
    assert anchor_prefix_sha256(base, "\n\n") == anchor_prefix_sha256(grown, "\n\n")
    changed = [*base[:3], _block(3, "user", "Remember:\nother\nchanged"), *base[4:]]
    assert anchor_prefix_sha256(changed, "\n\n") != anchor_prefix_sha256(base, "\n\n")
    short = compact_prompt_blocks(base, _cfg())
    long = compact_prompt_blocks(grown, _cfg())
    assert short.prompt_prefix_sha256 == long.prompt_prefix_sha256


def test_tool_pair_never_split() -> None:
    blocks = [
        _block(0, "system", "You are a test assistant."),
        _block(1, "user", "start the paired tool scenario"),
        _block(2, "assistant", f"[tool call {_PAIR_ID}] lookup_pair(pair-42)"),
        _block(
            3,
            "tool",
            f"[tool result {_PAIR_ID}] PAIR_RESULT_42 value=quokka-42 " + "y" * 2000,
        ),
    ]
    for turn in range(32):
        blocks.extend(_tool_turn(4 + turn * 3, turn))
    blocks.append(_block(100, "user", "Report the paired lookup value."))
    result = compact_prompt_blocks(blocks, _cfg())
    assert result.prompt_bytes <= _LIMIT
    has_call = f"[tool call {_PAIR_ID}]" in result.prompt
    has_result = f"[tool result {_PAIR_ID}]" in result.prompt
    assert has_call == has_result, "tool pair was split"
    if not has_call:
        assert _PAIR_ID in result.prompt, "digest lost digested tool call id"


def test_no_tool_ref_split_across_all_pairs() -> None:
    result = compact_prompt_blocks(_canary_blocks(), _cfg())
    for turn in range(32):
        call_id = "call_%02d" % turn
        has_call = f"[tool call {call_id}]" in result.prompt
        has_result = f"[tool result {call_id}]" in result.prompt
        assert has_call == has_result, f"pair {call_id} split"
        assert call_id in result.prompt, f"pair {call_id} lost without trace"


@pytest.mark.parametrize("limit", [16384, 32768, 98304, 262144, 524288])
def test_output_within_limit_across_range(limit: int) -> None:
    result = compact_prompt_blocks(_canary_blocks(), _cfg(limit))
    assert result.prompt_bytes <= limit
    assert result.limit_bytes == limit
    assert _CANARY in result.prompt


def test_deterministic_and_prefix_hash_stable() -> None:
    base = compact_prompt_blocks(_canary_blocks(20), _cfg())
    again = compact_prompt_blocks(_canary_blocks(20), _cfg())
    grown = compact_prompt_blocks(_canary_blocks(40), _cfg())
    assert base.prompt == again.prompt
    assert base.prompt_prefix_sha256 == again.prompt_prefix_sha256
    assert base.prompt_prefix_sha256 == grown.prompt_prefix_sha256
    assert _HEX64.match(base.prompt_prefix_sha256)


def test_prefix_hash_changes_with_anchor() -> None:
    blocks = _canary_blocks(4)
    changed = [_block(0, "system", "Different system prompt."), *blocks[1:]]
    assert compact_prompt_blocks(blocks, _cfg()).prompt_prefix_sha256 != (
        compact_prompt_blocks(changed, _cfg()).prompt_prefix_sha256
    )


def test_fitting_history_returned_unchanged() -> None:
    blocks = [
        _block(0, "system", "sys"),
        _block(1, "user", "hello"),
        _block(2, "assistant", "hi"),
    ]
    result = compact_prompt_blocks(blocks, _cfg())
    assert result.prompt == "\n\n".join(b.rendered for b in blocks)
    assert result.kept_count == 3
    assert result.digested_count == 0
    assert result.dropped_count == 0
    assert result.mode == "compact"


def test_empty_history() -> None:
    result = compact_prompt_blocks([], _cfg())
    assert result.prompt == ""
    assert result.prompt_bytes == 0
    assert result.kept_count == 0
    assert _HEX64.match(result.prompt_prefix_sha256)


def test_single_block() -> None:
    result = compact_prompt_blocks([_block(0, "user", "only one")], _cfg())
    assert result.prompt == "### 0. user\nonly one"
    assert result.kept_count == 1


def test_single_huge_block_controlled_degradation() -> None:
    blocks = [
        _block(0, "system", "sys"),
        _block(1, "user", "HUGE-HEAD " + "a" * 150000 + " HUGE-TAIL"),
    ]
    result = compact_prompt_blocks(blocks, _cfg())
    assert result.prompt_bytes <= _LIMIT
    assert "HUGE-HEAD" in result.prompt
    assert "HUGE-TAIL" in result.prompt
    assert DEFAULT_MIDDLE_PRUNED_MARKER in result.prompt


def test_only_tool_blocks() -> None:
    blocks = [
        _block(i, "tool", f"[tool result call_x{i}] " + "z" * 8000) for i in range(20)
    ]
    result = compact_prompt_blocks(blocks, _cfg(32768))
    assert result.prompt_bytes <= 32768
    assert "call_x19" in result.prompt


def test_unicode_and_json_escaping() -> None:
    assert json_text_bytes('строка "q" \\n') == len(
        'строка \\"q\\" \\\\n'.encode("utf-8")
    )
    blocks = [_block(i, "user", 'строка "q" \\n ' * 400) for i in range(12)]
    result = compact_prompt_blocks(blocks, _cfg(16384))
    assert result.prompt_bytes <= 16384
    assert result.prompt_bytes == json_text_bytes(result.prompt)


def test_middle_prune_text_contract() -> None:
    assert middle_prune_text("short", 100) == "short"
    pruned = middle_prune_text("head-" + "m" * 5000 + "-tail", 200)
    assert json_text_bytes(pruned) <= 200
    assert pruned.startswith("head-")
    assert pruned.endswith("-tail")
    assert DEFAULT_MIDDLE_PRUNED_MARKER in pruned
    tiny = middle_prune_text("abcdef", 3)
    assert json_text_bytes(tiny) <= 3


def test_digest_mentions_range_and_count() -> None:
    result = compact_prompt_blocks(_canary_blocks(), _cfg())
    assert "[сжатая история ходов " in result.prompt
    assert "сообщение" in result.prompt or "сообщений]" in result.prompt


def _imported_roots(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def _mutable_globals(tree: ast.Module) -> list[ast.stmt]:
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(node.value, (ast.List, ast.Dict, ast.Set))
    ]


def test_domain_purity_ast() -> None:
    path = BRIDGE_DIR / "agy_runtime" / "history_compaction_domain.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "os",
        "sys",
        "httpx",
        "subprocess",
        "fastapi",
        "pathlib",
        "logging",
        "time",
    }
    imported = _imported_roots(tree)
    assert not imported & forbidden
    assert "server" not in imported
    assert "long_session_config" not in imported
    assert not _mutable_globals(tree)


def test_anchor_without_user_stops_at_first_non_system() -> None:
    s0 = _block(0, "system", "S0")
    seq = [s0, _block(1, "tool", "T1"), _block(2, "system", "S2")]
    assert anchor_prefix_sha256(seq, "\n\n") == anchor_prefix_sha256([s0], "\n\n")


def _synthetic(index: int, body: str) -> PromptBlock:
    return _block(index, "user", body)


def test_session_3a8cf9f1_real_user_is_anchor_and_hash_input() -> None:
    approval = "The user approved the bash command."
    real = "SESSION_REAL_USER\nmultiline request\n" + "r" * 6000 + " REAL_USER_END"
    blocks = [
        _block(0, "system", "s" * 65000),
        _synthetic(1, approval),
        _block(2, "user", real),
        _synthetic(3, "<system-reminder>\nAGENTS.md\n" + "a" * 400 + "\n</system-reminder>"),
        _synthetic(
            4,
            'Current runtime context. This snapshot supersedes earlier snapshots.\n\n'
            'Current working directory: "/tmp/work".',
        ),
        _synthetic(5, "<system-reminder>\nskill-catalog\n" + "k" * 7000 + "\n</system-reminder>"),
    ]
    wide = compact_prompt_blocks(blocks, _cfg(72760))
    shifted = compact_prompt_blocks(blocks, _cfg(72760 - 276))
    changed = [*blocks[:2], _block(2, "user", real + " changed"), *blocks[3:]]
    assert "REAL_USER_END" in wide.prompt and "REAL_USER_END" in shifted.prompt
    assert wide.prompt.index(approval) < wide.prompt.index("SESSION_REAL_USER")
    assert wide.prompt_prefix_sha256 == shifted.prompt_prefix_sha256
    assert wide.prompt_prefix_sha256 != anchor_prefix_sha256(changed, "\n\n")


def test_last_real_turn_survives_trailing_large_system_reminder() -> None:
    blocks = [
        _block(0, "system", "sys"),
        _block(1, "user", "initial request"),
        _block(2, "assistant", "old answer " + "o" * 8000),
        _block(3, "user", "TURN_K_BEGIN\n" + "u" * 6000 + "\nTURN_K_END"),
        _synthetic(
            4,
            "<system-reminder>\nTRAILING_SERVICE_BLOCK\n"
            + "z" * 25000
            + "\n</system-reminder>",
        ),
    ]
    result = compact_prompt_blocks(blocks, _cfg(12000))
    assert result.prompt_bytes <= 12000
    assert "TURN_K_BEGIN" in result.prompt and "TURN_K_END" in result.prompt
    assert "TRAILING_SERVICE_BLOCK" not in result.prompt


def test_all_synthetic_last_user_is_protected_carrier() -> None:
    protected = "<system-reminder>\nLAST_SYNTHETIC_CARRIER\n</system-reminder>"
    blocks = [
        _block(0, "system", "sys"),
        _synthetic(1, "The user approved the bash command."),
        _synthetic(2, protected),
        _block(3, "assistant", "trailing output " + "x" * 20000),
    ]
    result = compact_prompt_blocks(blocks, _cfg(5000))
    assert result.prompt_bytes <= 5000
    assert "LAST_SYNTHETIC_CARRIER" in result.prompt


def test_overflow_marks_synthetic_users_but_not_fallback_carrier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    def capture(items: object, _spec: object) -> str:
        seen.extend(items)  # type: ignore[arg-type]
        return ""

    monkeypatch.setattr(compaction_domain, "shrink_overflow_parts", capture)
    compact_prompt_blocks(
        [
            _block(0, "system", "s" * 5000),
            _synthetic(1, "The user approved the bash command."),
            _synthetic(2, "<system-reminder>\nPROTECTED\n</system-reminder>"),
        ],
        _cfg(100),
    )
    roles = {text: role for role, text in seen}
    assert roles[next(text for text in roles if "approved" in text)] == "synthetic"
    assert roles[next(text for text in roles if "PROTECTED" in text)] == "user"

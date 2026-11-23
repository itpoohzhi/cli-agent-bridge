"""W6: граничные мутационные тесты компакции истории agy (adapter + domain)."""

from __future__ import annotations

import re
import sys
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.append(str(_ROOT / "bridges/agy-bridge"))

from agy_runtime.history_compaction_adapter import (  # noqa: E402
    CompactionAdapterRequest,
    RawBlock,
    _build_config,
    render_or_compact_blocks,
)
from agy_runtime.history_compaction_domain import (  # noqa: E402
    DEFAULT_INPUT_GUARD_BYTES,
    DEFAULT_MIDDLE_PRUNED_MARKER,
    CompactionConfig,
    PromptBlock,
    compact_prompt_blocks,
    json_text_bytes,
    middle_prune_text,
)

_CANARY = "CANARY_FACT_ALPHA_7391"
_LIMIT = 16384


def _block(index: int, role: str, body: str) -> PromptBlock:
    return PromptBlock(index, role, f"### {index}. {role}\n{body}")


def _cfg(limit: int, max_d: int = 16384, min_d: int = 1024, tail: int = 1):
    return CompactionConfig(limit, 0.20, min_d, max_d, tail)


def _pb_history(turns: int = 8) -> list[PromptBlock]:
    blocks = [
        _block(0, "system", "You are a test assistant."),
        _block(1, "user", f"Remember: {_CANARY} codename is LARCH-7391."),
    ]
    for turn in range(turns):
        cid, base = "call_%02d" % turn, 2 + turn * 3
        blocks.append(_block(base, "user", f"step {turn}: read chunk {turn}"))
        blocks.append(_block(base + 1, "assistant", f"[tool call {cid}] read()"))
        blocks.append(_block(base + 2, "tool", f"[tool result {cid}] " + "x" * 4200))
    blocks.append(_block(2 + turns * 3, "user", "What is the codename?"))
    return blocks


def _middle_history() -> list[PromptBlock]:
    blocks = [
        _block(0, "system", "sys"),
        _block(1, "user", "anchor CANARY"),
        _block(2, "assistant", "[tool call t1] do thing"),
        PromptBlock(3, "user", "\n\n### 3. user\n\nUNIQUE_BODY_SUMMARY_99\nsecond"),
        _block(4, "tool", "[tool result t1] ok"),
        _block(5, "user", "PLAIN_MIDDLE_42 normal text"),
        _block(6, "user", "FULL_ANNOUNCE_LINE_" + "x" * 80),
    ]
    blocks += [_block(7 + n, "user", f"FILL{n} " + "f" * 3000) for n in range(4)]
    blocks.append(_block(11, "user", "FINAL_QUESTION " + "y" * 2000))
    return blocks


def _rendered(item: RawBlock) -> str:
    return item.rendered if isinstance(item, PromptBlock) else str(item[-1])


def _joined_raw(blocks: object, tail_block: str, _limit: int) -> str:
    parts = [_rendered(item) for item in blocks]  # type: ignore[attr-defined]
    return "\n\n".join(parts + ([tail_block] if tail_block else [])).strip()


def _sentinel_legacy(_blocks: object, _tail: str, _limit: int) -> str:
    return "LEGACY_FALLBACK_RESULT"


def _base_req(blocks: list[RawBlock], enabled: bool, logs: list[str], cfg: Path):
    return CompactionAdapterRequest(
        blocks, "", _LIMIT, enabled, _joined_raw, logs.append, cfg
    )


def _log_value(logs: list[str], name: str) -> str:
    match = re.search(rf"{name}=(\S+)", "\n".join(logs))
    assert match is not None, f"log field {name} missing"
    return match.group(1)


@pytest.mark.parametrize("enabled", [False, True], ids=["legacy", "compact"])
def test_direct_prompt_block_input(tmp_path: Path, enabled: bool) -> None:
    blocks, logs = _pb_history(), []
    req = _base_req(list(blocks), enabled, logs, tmp_path / "dynamic_config.json")
    prompt = render_or_compact_blocks(req)
    assert _CANARY in prompt
    if enabled:
        assert json_text_bytes(prompt) <= _LIMIT
        assert _log_value(logs, "mode") == "compact"
    else:
        assert prompt == "\n\n".join(b.rendered for b in blocks).strip()
        assert _log_value(logs, "mode") == "legacy"


def test_default_size_fn_none_uses_json_bytes() -> None:
    logs: list[str] = []
    req = CompactionAdapterRequest(
        list(_pb_history()), "", _LIMIT, True, _joined_raw, logs.append
    )
    prompt = render_or_compact_blocks(req)
    assert _CANARY in prompt and _log_value(logs, "mode") == "compact"
    assert int(_log_value(logs, "prompt_bytes")) == json_text_bytes(prompt)
    assert json_text_bytes(prompt) <= _LIMIT


def test_empty_rendered_block_not_counted_dropped(tmp_path: Path) -> None:
    blocks: list[RawBlock] = [
        (0, "user", ""),
        (1, "user", "### 1. user\nKEEP_ME"),
        (2, "user", "### 2. user\nDROP_ME"),
    ]
    logs: list[str] = []
    req = _base_req(blocks, False, logs, tmp_path / "dynamic_config.json")
    render_or_compact_blocks(replace(req, limit_bytes=10))
    assert _log_value(logs, "dropped") == "0"
    logs.clear()
    keep_only = lambda _b, _t, _l: "### 1. user\nKEEP_ME"  # noqa: E731
    render_or_compact_blocks(replace(req, legacy_prune=keep_only))
    assert _log_value(logs, "dropped") == "1"


def test_legacy_overflow_unchanged_result_still_logs(tmp_path: Path) -> None:
    blocks: list[RawBlock] = [
        (0, "system", "### 0. system\nsys"),
        (1, "user", "### 1. user\n" + "a" * 500),
    ]
    logs: list[str] = []
    req = _base_req(blocks, False, logs, tmp_path / "dynamic_config.json")
    prompt = render_or_compact_blocks(replace(req, limit_bytes=100))
    assert json_text_bytes(prompt) > 100 and len(logs) == 1
    assert _log_value(logs, "mode") == "legacy"


def test_post_compact_over_limit_falls_back(tmp_path: Path) -> None:
    def inflated(text: str) -> int:
        return _LIMIT + 500 if "сжатая история" in text else json_text_bytes(text)

    logs: list[str] = []
    req = _base_req(list(_pb_history()), True, logs, tmp_path / "dynamic_config.json")
    prompt = render_or_compact_blocks(
        replace(req, size_fn=inflated, legacy_prune=_sentinel_legacy)
    )
    assert prompt == "LEGACY_FALLBACK_RESULT"
    assert _log_value(logs, "mode") == "fallback"
    assert _log_value(logs, "reason") == "over_limit"


def test_middle_prune_tiny_budget_exact_prefix() -> None:
    assert middle_prune_text("abcdef", 3) == "abc"


def _boundary_history(role: str, body: str) -> list[PromptBlock]:
    blocks = [_block(0, "system", "sys"), _block(1, "user", "anchor")]
    blocks += [_block(2 + n, "user", f"FILL{n} " + "f" * 3000) for n in range(3)]
    blocks.append(_block(5, role, body + " " + "a" * 3000 + " FIRST_TAIL_MARKER"))
    blocks.append(_block(6, "tool", "[tool result tX] " + "t" * 1500 + " TOOL_TAIL"))
    blocks.append(_block(7, "user", "FINAL " + "y" * 3000))
    return blocks


@pytest.mark.parametrize(
    "role,body",
    [
        ("assistant", "PLAIN_ASSISTANT_NO_CALL"),
        ("user", "[tool call x] USER_WITH_CALL"),
    ],
)
def test_tool_group_boundary_not_merged(role: str, body: str) -> None:
    result = compact_prompt_blocks(_boundary_history(role, body), _cfg(8000))
    assert "TOOL_TAIL" in result.prompt
    assert "FIRST_TAIL_MARKER" not in result.prompt


def test_first_content_line_skips_blanks_and_header() -> None:
    result = compact_prompt_blocks(_middle_history(), _cfg(12000, max_d=4096))
    assert "- #3 user: UNIQUE_BODY_SUMMARY_99" in result.prompt
    assert "- #3 user: ###" not in result.prompt


def test_digest_first_fitting_width_no_middle_prune() -> None:
    result = compact_prompt_blocks(_middle_history(), _cfg(12000, max_d=4096))
    assert "- #6 user: FULL_ANNOUNCE_LINE_" + "x" * 80 in result.prompt
    assert DEFAULT_MIDDLE_PRUNED_MARKER not in result.prompt


def test_digest_width_zero_keeps_tools_drops_plain() -> None:
    wide = compact_prompt_blocks(_middle_history(), _cfg(12000, max_d=4096))
    assert "- #5 user: PLAIN_MIDDLE_42 normal text" in wide.prompt
    narrow = compact_prompt_blocks(_middle_history(), _cfg(12000, 250, 250))
    assert "[tools: t1]" in narrow.prompt
    assert "- #5 user" not in narrow.prompt and "PLAIN_MIDDLE_42" not in narrow.prompt


def test_tail_keeps_first_group_even_over_budget() -> None:
    blocks = [
        _block(0, "system", "sys"),
        _block(1, "user", "anchor"),
        _block(2, "user", "MIDDLE_A " + "m" * 2000),
        _block(3, "user", "PENULTIMATE " + "p" * 2000 + " PENULT_TAIL_MARKER"),
        _block(4, "user", "LAST_GROUP " + "L" * 5000 + " LAST_TAIL_MARKER"),
    ]
    result = compact_prompt_blocks(blocks, _cfg(3000, max_d=500, min_d=0, tail=0))
    assert "LAST_GROUP" in result.prompt and "LAST_TAIL_MARKER" in result.prompt
    assert "PENULT_TAIL_MARKER" not in result.prompt and result.kept_count == 3


def test_multiple_tail_groups_preserved_when_fits() -> None:
    blocks = [_block(0, "system", "sys"), _block(1, "user", "anchor CANARY")]
    blocks += [_block(2 + n, "user", f"MIDDLE{n} " + "m" * 1500) for n in range(6)]
    blocks.append(_block(8, "user", "TAIL_ONE " + "a" * 1000 + " TAIL_ONE_END"))
    blocks.append(_block(9, "user", "TAIL_TWO " + "b" * 1000 + " TAIL_TWO_END"))
    result = compact_prompt_blocks(blocks, _cfg(4000))
    assert "TAIL_ONE_END" in result.prompt and "TAIL_TWO_END" in result.prompt
    assert result.kept_count == 4


def test_prompt_block_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        _block(0, "user", "hello").role = "system"  # type: ignore[misc]


def test_compaction_config_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        _cfg(1000).limit_bytes = 2000  # type: ignore[misc]


def test_legacy_unchanged_under_limit_emits_no_log() -> None:
    logs: list[str] = []
    blocks = [_block(0, "system", "sys"), _block(1, "user", "tiny")]
    full = "\n\n".join(b.rendered for b in blocks)
    req = CompactionAdapterRequest(
        blocks=blocks,
        tail_block="",
        limit_bytes=2000,
        enabled=False,
        legacy_prune=lambda _b, _t, _l: full,
        log_fn=logs.append,
    )
    assert render_or_compact_blocks(req) == full
    assert logs == []


def test_tail_tool_pair_stays_atomic_when_budget_tight() -> None:
    blocks = [
        _block(0, "system", "sys"),
        _block(1, "user", "anchor CANARY"),
        _block(2, "user", "MIDDLE_FILL " + "m" * 4000),
        _block(3, "assistant", "[tool call pair_tail] fetch() " + "a" * 1800),
        _block(
            4, "tool", "[tool result pair_tail] ok " + "t" * 1800 + " PAIR_TAIL_END"
        ),
    ]
    result = compact_prompt_blocks(blocks, _cfg(2600, max_d=400, min_d=0, tail=1))
    assert "[tool call pair_tail]" in result.prompt
    assert "PAIR_TAIL_END" in result.prompt
    assert result.kept_count == 4
    assert result.digested_count == 1


def test_adapter_defaults_are_domain_ssot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    by_name = {f.name: f for f in fields(CompactionAdapterRequest)}
    assert by_name["input_guard_bytes"].default == DEFAULT_INPUT_GUARD_BYTES
    logs: list[str] = []
    cfg_path = tmp_path / "dynamic_config.json"
    req = _base_req(list(_pb_history()), True, logs, cfg_path)
    built = _build_config(req)
    reference = CompactionConfig(
        limit_bytes=built.limit_bytes,
        middle_pruned_marker=req.middle_pruned_marker,
        separator=req.separator,
    )
    assert built == reference
    baseline = render_or_compact_blocks(req)
    for suffix in ("DIGEST_RATIO", "MIN_DIGEST_BYTES", "MAX_DIGEST_BYTES"):
        monkeypatch.setenv(f"AGY_HISTORY_COMPACTION_{suffix}", "1")
    monkeypatch.setenv("AGY_HISTORY_COMPACTION_TAIL_MIN_GROUPS", "9")
    monkeypatch.setenv("AGY_HISTORY_COMPACTION_INPUT_GUARD_BYTES", "1")
    cfg_path.write_text('{"history_compaction_digest_ratio": 1}', encoding="utf-8")
    assert render_or_compact_blocks(req) == baseline

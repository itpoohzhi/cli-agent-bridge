"""W1-F: compact tools only with cid-bound fingerprint proof (VER-009, AD-013).

Deterministic domain unit tests: 0 sockets, 0 sleep, 0 env access.
PROVEN requires resumed + stored_fp == current_fp + fp committed for the
same cid; explicit path and cold turns get full schemas. LEGACY reproduces
the pre-fix decision; OFF never compacts.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Final

import pytest

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.resumed_tools_policy import (  # noqa: E402
    CompactToolsMode,
    CompactToolsQuery,
    compute_tools_fingerprint,
    decide_compact_tools,
    should_use_compact_tools,
)

_TOOLS: Final[list[dict[str, object]]] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the index",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    }
]
_FP: Final[str] = compute_tools_fingerprint(_TOOLS, "auto")
_CID: Final[str] = "cid-proof-0001"


def _proven() -> CompactToolsQuery:
    return CompactToolsQuery(
        is_resumed=True,
        stored_fp=_FP,
        stored_cid=_CID,
        run_cid=_CID,
        tools=_TOOLS,
        tool_choice="auto",
    )


def test_proven_full_proof_compacts() -> None:
    assert decide_compact_tools(_proven()) is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stored_fp", ""),
        ("stored_fp", "0" * 64),
        ("stored_cid", ""),
        ("stored_cid", "cid-other"),
        ("run_cid", ""),
        ("is_resumed", False),
        ("explicit_path", True),
        ("compact_enabled", False),
        ("emulate_tools", False),
        ("tool_choice", "required"),
    ],
)
def test_proven_missing_proof_falls_back_to_full(field: str, value: object) -> None:
    query = replace(_proven(), **{field: value})
    assert decide_compact_tools(query) is False


def test_proven_cid_mismatch_rejects_equal_fingerprint() -> None:
    """Split-brain guard: fp committed for another cid is not a proof."""
    query = replace(_proven(), stored_cid="cid-previous-conversation")
    assert query.stored_fp == compute_tools_fingerprint(query.tools, query.tool_choice)
    assert decide_compact_tools(query) is False


def test_proven_attachment_contract_is_part_of_proof() -> None:
    attached_fp = compute_tools_fingerprint(
        _TOOLS, "auto", has_attachments=True, attachment_tool="read"
    )
    query = replace(
        _proven(), stored_fp=attached_fp, has_attachments=True, attachment_tool="read"
    )
    assert decide_compact_tools(query) is True
    dropped = replace(query, has_attachments=False, attachment_tool=None)
    assert decide_compact_tools(dropped) is False


def test_proven_tool_key_order_does_not_break_proof() -> None:
    reordered = [dict(reversed(list(tool.items()))) for tool in _TOOLS]
    assert decide_compact_tools(replace(_proven(), tools=reordered)) is True


def test_proven_decision_delegates_to_should_use_compact_tools() -> None:
    for resumed in (False, True):
        for enabled in (False, True):
            query = replace(_proven(), is_resumed=resumed, compact_enabled=enabled)
            expected = should_use_compact_tools(resumed, _FP, _FP, enabled)
            assert decide_compact_tools(query) is expected


def test_explicit_path_proven_full_but_legacy_compacts() -> None:
    explicit = replace(_proven(), explicit_path=True, stored_fp="", stored_cid="")
    assert decide_compact_tools(explicit) is False
    legacy = replace(explicit, mode=CompactToolsMode.LEGACY)
    assert decide_compact_tools(legacy) is True


def test_cold_turn_gets_full_schemas() -> None:
    cold = replace(_proven(), is_resumed=False)
    assert decide_compact_tools(cold) is False
    assert decide_compact_tools(replace(cold, mode=CompactToolsMode.LEGACY)) is False


def test_off_never_compacts() -> None:
    off = replace(_proven(), mode=CompactToolsMode.OFF)
    assert decide_compact_tools(off) is False
    assert decide_compact_tools(replace(off, explicit_path=True)) is False
    assert decide_compact_tools(replace(off, compact_enabled=True)) is False


@pytest.mark.parametrize("resumed", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("emulate", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("fp_kind", ["match", "changed", "empty"])
def test_legacy_mode_reproduces_pre_fix_decision(
    resumed: bool, explicit: bool, emulate: bool, enabled: bool, fp_kind: str
) -> None:
    current_fp = compute_tools_fingerprint(_TOOLS, "auto") if emulate else ""
    stored_fp = {"match": current_fp, "changed": "f" * 64, "empty": ""}[fp_kind]
    query = CompactToolsQuery(
        mode=CompactToolsMode.LEGACY,
        is_resumed=resumed,
        explicit_path=explicit,
        emulate_tools=emulate,
        compact_enabled=enabled,
        stored_fp=stored_fp,
        tools=_TOOLS,
        tool_choice="auto",
    )
    if explicit:
        expected = emulate and enabled
    else:
        expected = should_use_compact_tools(resumed, stored_fp, current_fp, enabled)
    assert decide_compact_tools(query) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("proven", CompactToolsMode.PROVEN),
        ("legacy", CompactToolsMode.LEGACY),
        ("off", CompactToolsMode.OFF),
        (" LEGACY ", CompactToolsMode.LEGACY),
        ("Off", CompactToolsMode.OFF),
        ("", CompactToolsMode.PROVEN),
        ("bogus", CompactToolsMode.PROVEN),
        (None, CompactToolsMode.PROVEN),
        (7, CompactToolsMode.PROVEN),
    ],
)
def test_mode_parse_fail_closed(raw: object, expected: CompactToolsMode) -> None:
    assert CompactToolsMode.parse(raw) is expected


def test_query_is_frozen() -> None:
    query = _proven()
    with pytest.raises(FrozenInstanceError):
        query.run_cid = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "proven"},
        {"mode": None},
        {"is_resumed": 1},
        {"explicit_path": "yes"},
        {"emulate_tools": None},
        {"compact_enabled": 0},
        {"has_attachments": "true"},
        {"stored_fp": None},
        {"stored_cid": 42},
        {"run_cid": b"cid"},
    ],
)
def test_query_validation_fail_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must be"):
        CompactToolsQuery(**kwargs)  # type: ignore[arg-type]


def test_defaults_are_fail_closed() -> None:
    query = CompactToolsQuery()
    assert query.mode is CompactToolsMode.PROVEN
    assert query.is_resumed is False
    assert decide_compact_tools(query) is False


_BANNED_IMPORTS: Final = frozenset(
    {
        "os",
        "subprocess",
        "threading",
        "socket",
        "httpx",
        "openai",
        "requests",
        "aiohttp",
        "urllib3",
        "fastapi",
        "litestar",
        "starlette",
        "sqlalchemy",
        "redis",
        "time",
    }
)
_MUTABLE_CTOR: Final = frozenset({"dict", "list", "set", "defaultdict", "deque"})


def test_module_is_pure_domain_no_io_env_or_mutable_state() -> None:
    """M-MOD-I3/I4: static purity of the domain module (BND-001)."""
    import core.resumed_tools_policy as policy

    module_file = policy.__file__
    assert module_file is not None
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
            assert not roots & _BANNED_IMPORTS, f"banned import: {roots}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in _BANNED_IMPORTS
        elif isinstance(node, ast.Attribute):
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            ), "os.environ access in pure domain"
    for stmt in tree.body:
        targets = (
            stmt.targets
            if isinstance(stmt, ast.Assign)
            else [getattr(stmt, "target", None)]
        )
        if any(
            isinstance(t, ast.Name) and t.id in ("__all__", "__slots__")
            for t in targets
        ):
            continue
        value = stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
        if value is None:
            continue
        assert not isinstance(
            value,
            (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp),
        ), "module-level mutable collection"
        if isinstance(value, ast.Call):
            name = (
                value.func.id
                if isinstance(value.func, ast.Name)
                else getattr(value.func, "attr", "")
            )
            assert name not in _MUTABLE_CTOR, "module-level mutable collection"

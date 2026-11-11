"""Контракт чистой классификации generic PRE-COMMIT сбоя upstream."""

from __future__ import annotations

import __future__
import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

import core.precommit_timeout_policy as policy
from core.precommit_timeout_policy import (
    PreCommitFailureClass,
    classify_precommit_generic_failure,
)


@pytest.mark.parametrize(
    ("now_s", "current_deadline_s", "cap_deadline_s", "expected"),
    [
        (9.0, 10.0, 10.0, PreCommitFailureClass.UPSTREAM_UNAVAILABLE),
        (10.0, 10.0, 10.0, PreCommitFailureClass.TIMEOUT),
        (11.0, 10.0, 10.0, PreCommitFailureClass.TIMEOUT),
        (19.0, 20.0, 20.0, PreCommitFailureClass.UPSTREAM_UNAVAILABLE),
        (20.0, 20.0, 20.0, PreCommitFailureClass.TIMEOUT),
        (29.0, 30.0, 40.0, PreCommitFailureClass.UPSTREAM_UNAVAILABLE),
        (30.0, 30.0, 40.0, PreCommitFailureClass.TIMEOUT),
        (40.0, 50.0, 40.0, PreCommitFailureClass.TIMEOUT),
        (51.0, 50.0, 40.0, PreCommitFailureClass.TIMEOUT),
    ],
    ids=[
        "static-live",
        "static-equality",
        "static-expired",
        "unarmed-live",
        "unarmed-equality",
        "armed-live",
        "armed-current-equality",
        "armed-cap-equality",
        "armed-past-both",
    ],
)
def test_truth_table(
    now_s: float,
    current_deadline_s: float,
    cap_deadline_s: float,
    expected: PreCommitFailureClass,
) -> None:
    assert (
        classify_precommit_generic_failure(
            now_s=now_s,
            current_deadline_s=current_deadline_s,
            cap_deadline_s=cap_deadline_s,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("now_s", None),
        ("current_deadline_s", None),
        ("cap_deadline_s", None),
        ("now_s", 1),
        ("current_deadline_s", 1),
        ("cap_deadline_s", 1),
        ("now_s", "10"),
        ("current_deadline_s", "10"),
        ("cap_deadline_s", "10"),
        ("now_s", float("nan")),
        ("current_deadline_s", float("nan")),
        ("cap_deadline_s", float("nan")),
        ("now_s", float("inf")),
        ("current_deadline_s", float("inf")),
        ("cap_deadline_s", float("inf")),
        ("now_s", float("-inf")),
        ("current_deadline_s", float("-inf")),
        ("cap_deadline_s", float("-inf")),
    ],
)
def test_invalid_evidence_is_deterministic_upstream_unavailable(
    field: str, invalid: Any
) -> None:
    evidence: dict[str, Any] = {
        "now_s": 20.0,
        "current_deadline_s": 10.0,
        "cap_deadline_s": 10.0,
    }
    evidence[field] = invalid
    assert (
        classify_precommit_generic_failure(**evidence)
        is PreCommitFailureClass.UPSTREAM_UNAVAILABLE
    )


def test_same_valid_inputs_always_produce_same_result() -> None:
    outcomes = {
        classify_precommit_generic_failure(
            now_s=9.0,
            current_deadline_s=10.0,
            cap_deadline_s=11.0,
        )
        for _ in range(10)
    }
    assert outcomes == {PreCommitFailureClass.UPSTREAM_UNAVAILABLE}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"current_deadline_s": 10.0, "cap_deadline_s": 10.0},
        {"now_s": 10.0, "cap_deadline_s": 10.0},
        {"now_s": 10.0, "current_deadline_s": 10.0},
    ],
)
def test_omitted_keyword_is_binding_error(kwargs: dict[str, float]) -> None:
    with pytest.raises(TypeError):
        classify_precommit_generic_failure(**kwargs)  # type: ignore[arg-type]


def test_public_surface_and_enum_members_are_exact() -> None:
    public_symbols = {name for name in vars(policy) if not name.startswith("_")}
    annotations_feature = vars(policy).get("annotations")
    if annotations_feature is not None:
        assert annotations_feature is __future__.annotations
        public_symbols.remove("annotations")
    assert public_symbols == {
        "PreCommitFailureClass",
        "classify_precommit_generic_failure",
    }
    assert policy.__all__ == (
        "PreCommitFailureClass",
        "classify_precommit_generic_failure",
    )
    assert list(PreCommitFailureClass.__members__) == [
        "TIMEOUT",
        "UPSTREAM_UNAVAILABLE",
    ]


def test_module_is_small_and_pure() -> None:
    source_path = Path(inspect.getsourcefile(policy) or "")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    nonblank_lines = [line for line in source.splitlines() if line.strip()]
    assert len(nonblank_lines) <= 120

    forbidden_import_parts = {
        "adapters",
        "bridges",
        "http",
        "liveness",
        "os",
        "server",
        "sliding",
        "socket",
        "threading",
        "time",
    }
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not {
        part
        for imported in imports
        for part in imported.split(".")
        if part in forbidden_import_parts
    }

    assert not [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(value, (ast.List, ast.Dict, ast.Set)) for value in ast.walk(node)
        )
    ]
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "classify_precommit_generic_failure"
    )
    statements = sum(isinstance(node, ast.stmt) for node in ast.walk(function))
    match_nodes = (ast.Match,) if hasattr(ast, "Match") else ()
    branches = sum(
        isinstance(node, (ast.If, ast.IfExp, *match_nodes))
        for node in ast.walk(function)
    )
    assert statements <= 30
    assert branches <= 3

"""L1 Zero-I/O unit tests for core/p12_flag_and_params.py (W01)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.p12_flag_and_params import (
    ALL_P12_FLAGS,
    FLAG_AGY_ORPHAN_COORDINATOR,
    FLAG_AGY_PGID_QUARANTINE,
    FLAG_GEO_PRERELAY_DISCONNECT,
    FLAG_HUB_NONDETACHED_CANCEL,
    FLAG_HUB_RESIDENT_WIRING,
    FLAG_HUB_TURN_MODE_PROPAGATION,
    FLAG_ZEN_PGID_QUARANTINE,
    PGID_PROVENANCE_GATED_FLAGS,
    CleanupParamSnapshot,
    ParamSourceMissingError,
    SourcedParam,
    parse_bool_strict,
    resolve_flag,
    resolve_flag_with_params,
    validate_cleanup_params,
)


def _valid_params(service: str = "agy") -> CleanupParamSnapshot:
    return CleanupParamSnapshot(
        service=service,
        term_grace_s=SourcedParam(2.0, "agy:AGY_BRIDGE_KILL_TERM_GRACE_S"),
        poll_interval_s=SourcedParam(0.25, "agy:AGY_BRIDGE_KILL_INT_GRACE_S"),
        leader_wait_s=SourcedParam(5.0, "agy:AGY_BRIDGE_KILL_WAIT_S"),
    )


def test_all_seven_flags_default_false() -> None:
    assert len(ALL_P12_FLAGS) == 7
    for flag in ALL_P12_FLAGS:
        res = resolve_flag(flag, None, {})
        assert res.enabled is False
        assert res.origin == "default_false"


@pytest.mark.parametrize(
    ("json_snap", "env_snap", "json_invalid", "expected", "origin"),
    [
        ({FLAG_AGY_PGID_QUARANTINE: False}, {FLAG_AGY_PGID_QUARANTINE: "1"}, False, False, "dynamic_json"),
        ({FLAG_AGY_PGID_QUARANTINE: True}, {FLAG_AGY_PGID_QUARANTINE: "0"}, False, True, "dynamic_json"),
        ({FLAG_AGY_PGID_QUARANTINE.lower(): "true"}, {FLAG_AGY_PGID_QUARANTINE: "false"}, False, True, "dynamic_json"),
        ({FLAG_AGY_PGID_QUARANTINE.lower(): "false"}, {FLAG_AGY_PGID_QUARANTINE: "true"}, False, False, "dynamic_json"),
        ({}, {FLAG_AGY_PGID_QUARANTINE: "true"}, False, True, "env"),
        ({}, {FLAG_AGY_PGID_QUARANTINE: "1"}, False, True, "env"),
        ({}, {FLAG_AGY_PGID_QUARANTINE: "0"}, False, False, "env"),
        (None, {FLAG_AGY_PGID_QUARANTINE: "maybe"}, False, False, "env_invalid_fail_closed"),
        ({FLAG_AGY_PGID_QUARANTINE: "maybe"}, {FLAG_AGY_PGID_QUARANTINE: "1"}, False, False, "json_invalid_value_fail_closed"),
        ({FLAG_AGY_PGID_QUARANTINE: True}, {FLAG_AGY_PGID_QUARANTINE: "1"}, True, False, "json_invalid_fail_closed"),
    ],
)
def test_golden_precedence_vectors(
    json_snap: dict[str, object] | None,
    env_snap: dict[str, str],
    json_invalid: bool,
    expected: bool,
    origin: str,
) -> None:
    res = resolve_flag(FLAG_AGY_PGID_QUARANTINE, json_snap, env_snap, json_invalid=json_invalid)
    assert res.enabled is expected
    assert res.origin == origin


def test_parse_bool_strict_edge_cases() -> None:
    assert parse_bool_strict(True) is True
    assert parse_bool_strict(False) is False
    assert parse_bool_strict(1) is True
    assert parse_bool_strict(0) is False
    assert parse_bool_strict(2) is None
    assert parse_bool_strict("YES") is True
    assert parse_bool_strict("off") is False
    assert parse_bool_strict("") is False
    assert parse_bool_strict("unknown") is None


def test_validate_cleanup_params_requires_provenance() -> None:
    ok = validate_cleanup_params(_valid_params("agy"))
    assert ok.service == "agy"
    assert ok.term_grace_s == 2.0
    assert ok.poll_interval_s == 0.25
    assert ok.leader_wait_s == 5.0

    with pytest.raises(ParamSourceMissingError):
        validate_cleanup_params(
            CleanupParamSnapshot(
                service="agy",
                term_grace_s=SourcedParam(2.0, ""),
                poll_interval_s=SourcedParam(0.25, "agy:config"),
                leader_wait_s=SourcedParam(5.0, "agy:config"),
            )
        )
    with pytest.raises(ParamSourceMissingError):
        validate_cleanup_params(
            CleanupParamSnapshot(
                service="agy",
                term_grace_s=SourcedParam(2.0, "agy:config"),
                poll_interval_s=SourcedParam(0.0, "agy:config"),
                leader_wait_s=SourcedParam(5.0, "agy:config"),
            )
        )


def test_param_source_missing_disables_only_pgid_flags_1_and_2() -> None:
    assert PGID_PROVENANCE_GATED_FLAGS == frozenset({FLAG_AGY_PGID_QUARANTINE, FLAG_ZEN_PGID_QUARANTINE})
    bad_params = CleanupParamSnapshot("agy", None, SourcedParam(0.25, "cfg"), SourcedParam(5.0, "cfg"))

    for pgid_flag in (FLAG_AGY_PGID_QUARANTINE, FLAG_ZEN_PGID_QUARANTINE):
        res = resolve_flag_with_params(pgid_flag, {pgid_flag: True}, {}, bad_params)
        assert res.enabled is False
        assert res.origin == "param_source_missing"

        res_ok = resolve_flag_with_params(pgid_flag, {pgid_flag: True}, {}, _valid_params())
        assert res_ok.enabled is True
        assert res_ok.origin == "dynamic_json"

    for non_pgid_flag in (
        FLAG_AGY_ORPHAN_COORDINATOR,
        FLAG_HUB_NONDETACHED_CANCEL,
        FLAG_HUB_RESIDENT_WIRING,
        FLAG_HUB_TURN_MODE_PROPAGATION,
        FLAG_GEO_PRERELAY_DISCONNECT,
    ):
        res = resolve_flag_with_params(non_pgid_flag, {non_pgid_flag: True}, {}, bad_params)
        assert res.enabled is True
        assert res.origin == "dynamic_json"


def test_module_is_strictly_zero_io() -> None:
    src = Path(__file__).resolve().parents[1] / "core/p12_flag_and_params.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    forbidden = {"os", "subprocess", "socket", "time", "pathlib", "ctypes", "select", "selectors"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden

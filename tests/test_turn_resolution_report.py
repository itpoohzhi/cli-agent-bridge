"""L1: отчёт `turn-resolved` и поля `/health` (AD-009, VER-010)."""

from __future__ import annotations

import ast
import sys
from dataclasses import replace
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import core.turn_resolution_report as report_mod  # noqa: E402
from core.transport_failure_contracts import (  # noqa: E402
    FLAG_ENV_BY_FIELD,
    FailureKind,
    RecoveryFlagSnapshot,
)
from core.turn_resolution_report import (  # noqa: E402
    build_turn_resolution_report,
    flags_snapshot_dict,
    format_turn_resolved,
    health_fields,
)


def test_flags_dict_has_six_env_names_in_fixed_order_default_false() -> None:
    snap = flags_snapshot_dict(RecoveryFlagSnapshot())
    assert list(snap) == [env for _, env in FLAG_ENV_BY_FIELD]
    assert len(snap) == 6 and not any(snap.values())


def test_flags_dict_reflects_enabled_flags() -> None:
    flags = replace(RecoveryFlagSnapshot(), toolcall_error_recovery=True, vendor_retry_phrase_mask=True)
    snap = flags_snapshot_dict(flags)
    assert snap["BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED"] is True
    assert snap["BRIDGE_VENDOR_RETRY_PHRASE_MASK_ENABLED"] is True
    assert sum(snap.values()) == 2


def test_format_is_deterministic_single_line() -> None:
    rep = build_turn_resolution_report("invisible_retry_ok", None, 2, FailureKind.NETWORK_TRANSIENT)
    line = format_turn_resolved(rep)
    assert line == "turn-resolved reason=invisible_retry_ok kind=network_transient attempts=2 flags_on=none"
    assert line == format_turn_resolved(rep)


def test_format_lists_enabled_flags_by_field_name() -> None:
    flags = replace(RecoveryFlagSnapshot(), transport_failure_classifier=True, retry_window_pause=True)
    line = format_turn_resolved(build_turn_resolution_report("r", flags))
    assert line.endswith("flags_on=transport_failure_classifier,retry_window_pause")


@pytest.mark.parametrize("reason", ["a\nb", "x\r\ny", "tab\there", "sp ace", "ключ значение", "ok=1 token=secret"])
def test_reason_cannot_break_the_line_or_inject_fields(reason: str) -> None:
    line = format_turn_resolved(build_turn_resolution_report(reason))
    assert "\n" not in line and "\r" not in line and " " not in line
    assert line.count("reason=") == 1
    assert line.split(" ")[1].startswith("reason=")
    assert len(line.split(" ")) == 5


@pytest.mark.parametrize("reason", ["", "   ", "\n"])
def test_empty_reason_becomes_none_token(reason: str) -> None:
    assert build_turn_resolution_report(reason).reason == "none"


def test_long_reason_is_bounded() -> None:
    rep = build_turn_resolution_report("x" * 5000)
    assert len(rep.reason) == report_mod.MAX_REASON_CHARS


def test_negative_attempts_are_clamped_to_zero() -> None:
    rep = build_turn_resolution_report("r", None, -4)
    assert rep.attempts == 0 and " attempts=0 " in format_turn_resolved(rep)


def test_health_fields_are_additive_and_json_friendly() -> None:
    rep = build_turn_resolution_report("recovered", RecoveryFlagSnapshot(toolcall_error_recovery=True))
    fields = health_fields(rep)
    assert set(fields) == {"resilience_flags", "last_turn_resolved"}
    assert fields["resilience_flags"]["BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED"] is True  # type: ignore[index]
    assert str(fields["last_turn_resolved"]).startswith("turn-resolved reason=recovered")


def test_no_secrets_or_paths_in_output() -> None:
    line = format_turn_resolved(build_turn_resolution_report("Bearer abc /Users/x/token"))
    assert "/" not in line and " " not in line.split("reason=")[1].split(" ")[0]


def test_module_is_pure_without_forbidden_imports() -> None:
    tree = ast.parse(Path(report_mod.__file__).read_text(encoding="utf-8"))
    names = {
        a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    } | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not names & {"os", "time", "threading", "subprocess", "socket", "asyncio", "server"}

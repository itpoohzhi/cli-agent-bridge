"""Дополнительные оракулы ветвей, обнаруженных мутационным прогоном C23."""

from __future__ import annotations

import io
import json
import queue
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from core import gateway_execution_policy as policy
from tools import droid_image, droid_probe_config


def test_mutating_prefix_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", " builder-, WRITER- ,, ")
    assert policy.resolve_autonomy("low", "DROID", subagent_id="Writer-1") == "low"
    with pytest.raises(policy.AutonomyViolation, match="requires mutating subagent"):
        policy.resolve_autonomy("medium", "DROID", subagent_id="coder-1")
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    with pytest.raises(policy.AutonomyViolation):
        policy.resolve_autonomy("low", "DROID", subagent_id="", require_subagent=True)


def test_mutating_library_opt_out_does_not_disable_http_or_explicit_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    assert policy.resolve_autonomy("medium", "DROID") == "medium"
    for identity in ("", "explorer-1"):
        with pytest.raises(policy.AutonomyViolation):
            policy.resolve_autonomy("medium", "DROID", subagent_id=identity)
    with pytest.raises(policy.AutonomyViolation):
        policy.resolve_autonomy("medium", "DROID", require_subagent=True)


def test_non_droid_namespace_keeps_its_mutating_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "1")
    assert (
        policy.resolve_autonomy("medium", "MUSE", subagent_id="explorer-1") == "medium"
    )


def test_settings_notification_returns_actual_readback() -> None:
    rpc = object.__new__(droid_image._Rpc)
    rpc.inbox = queue.Queue()
    settings = {"modelId": "model", "autonomyLevel": "off"}
    rpc.inbox.put(
        {"params": {"notification": {"type": "settings_updated", "settings": settings}}}
    )
    assert rpc.wait_settings() == settings


@pytest.mark.parametrize(
    "notification",
    [
        {"type": "other", "settings": {}},
        {"type": "settings_updated", "settings": "not-a-dict"},
    ],
)
def test_settings_from_notes_ignores_non_settings_or_invalid_payload(
    notification: dict[str, object],
) -> None:
    assert droid_image._settings_from_notes([{"notification": notification}]) is None


def test_rpc_reader_keeps_first_protocol_and_ignores_non_string_versions() -> None:
    frames = [
        {"factoryProtocolVersion": "first"},
        {"factoryProtocolVersion": "different"},
        {"factoryProtocolVersion": 1},
    ]
    rpc = object.__new__(droid_image._Rpc)
    rpc.proc = cast(
        "subprocess.Popen[bytes]",
        cast(
            object,
            SimpleNamespace(
                stdout=io.BytesIO(
                    b"".join(json.dumps(frame).encode() + b"\n" for frame in frames)
                ),
            ),
        ),
    )
    rpc.inbox = queue.Queue()
    rpc.protocol = ""
    rpc._read()
    assert rpc.protocol == "first"
    assert [rpc.inbox.get_nowait() for _ in frames] == frames
    assert rpc.inbox.get_nowait() is None


@pytest.mark.parametrize(
    "model",
    [
        {"id": 1, "efforts": ["high"], "default_effort": "high"},
        {"id": "", "efforts": ["high"], "default_effort": "high"},
        {"id": "model", "efforts": "high", "default_effort": "high"},
        {"id": "model", "efforts": [1], "default_effort": "high"},
        {"id": "model", "efforts": ["low"], "default_effort": "high"},
    ],
)
def test_probe_targets_reject_partial_fleet_types(
    tmp_path: Path,
    model: dict[str, object],
) -> None:
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps({"models": [{"backend": "droid", **model}]}))
    with pytest.raises(droid_probe_config.ProbeError):
        droid_probe_config.load_droid_probe_targets(path)

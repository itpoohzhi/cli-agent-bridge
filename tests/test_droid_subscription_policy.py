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
from tests.bridge_testlib import make_receipt
from tools import droid_image, droid_probe_config, receipt_schema


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


# --- Cycle 25 (Council C24): F-001, F-002, F-012, F-013, F-018, F-019 -------------


@pytest.mark.parametrize("value", [",", "*", " , * "])
def test_mutating_prefixes_reject_empty_and_wildcard(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """F-012: `,` и `*` в env не превращаются в разрешение всем ролям."""
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", value)
    assert policy.resolve_autonomy("low", "DROID", subagent_id="coder-1") == "low"
    with pytest.raises(policy.AutonomyViolation, match="requires mutating subagent"):
        policy.resolve_autonomy("low", "DROID", subagent_id="explorer-1")


@pytest.mark.parametrize("value", [",", "*"])
def test_deny_prefixes_fall_back_to_namespace_default(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """F-018/F-012: пустой или дикий deny-список откатывается на дефолт namespace."""
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", value)
    assert policy.denied_subagent("DROID", "panel-judge-k1") is True
    assert policy.denied_subagent("DROID", None, "JUDGE-1") is True
    assert policy.denied_subagent("DROID", None, "") is False
    assert policy.denied_subagent("DROID", "coder-c25") is False


def test_deny_prefixes_are_read_per_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-018: префиксы запрета читаются из env по namespace, без хардкода в шлюзе."""
    monkeypatch.setenv("MUSE_DENY_SUBAGENT_PREFIXES", " judge- , ,")
    assert policy.denied_subagent("MUSE", "judge-7") is True
    assert policy.denied_subagent("MUSE", "panel-judge-k1") is False


def test_library_default_call_does_not_enforce_mutating_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-013: библиотечный вызов без роли остаётся разрешённым при явном opt-out."""
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    decision = policy.resolve_autonomy_decision("low", "DROID")
    assert (decision.value, decision.source) == ("low", "request")


@pytest.mark.parametrize("bad", [5, {"level": "high"}, "ultra", ["low"]])
def test_format_only_validation_rejects_invalid_autonomy(bad: object) -> None:
    """F-001: базовая проверка формата не принимает типы и значения вне контракта."""
    with pytest.raises(policy.AutonomyViolation) as excinfo:
        policy.validate_autonomy_request(bad)
    assert excinfo.value.reason == "unsupported_autonomy"


@pytest.mark.parametrize(
    "raw,want", [(None, ""), ("", ""), (" ", ""), ("off", "off"), (" high ", "high")]
)
def test_format_only_validation_keeps_valid_levels(raw: object, want: str) -> None:
    assert policy.validate_autonomy_request(raw) == want


class _FakePopen:
    """Минимум полей, которые читает RPC-клиент при конструировании."""

    pid = 4242
    stdin = io.BytesIO()
    stdout = io.BytesIO(b"")

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_rpc_starts_at_zero_and_reader_is_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-013: нумерация запросов начинается с нуля, читатель не держит выход."""
    monkeypatch.setattr(
        droid_image.subprocess, "Popen", lambda *args, **kwargs: _FakePopen()
    )
    rpc = droid_image._Rpc(Path("/fake/image"), Path("/tmp"), Path("/tmp"))
    assert rpc._next == 0
    assert rpc._reader.daemon is True


def test_probe_facts_single_target_keeps_per_pair_evidence() -> None:
    """F-019/F-013: поуровневое доказательство строится и для единственной цели."""
    target = droid_probe_config.ProbeTarget("gpt-6.1-sol", "low")
    settings = set(receipt_schema.SETTINGS_PROFILE)
    facts = droid_image._probe_facts((target,), [("proto-1", {"Read"}, settings)])
    assert facts["protocol_version"] == "proto-1"
    assert facts["qualified_targets"] == [{"model": "gpt-6.1-sol", "effort": "low"}]
    assert facts["qualified_models"] == {"gpt-6.1-sol": ["Read"]}
    assert facts["readback"]["confirmed"] == sorted(settings)


def test_receipt_keeps_qualified_targets_and_rejects_tampering() -> None:
    """F-019: поуровневая квалификация всех пар хранится в receipt и проверяема."""
    receipt = make_receipt(Path("/fake/image"), "a" * 64)
    expected = [
        {"model": target.model, "effort": target.effort}
        for target in droid_probe_config.load_droid_probe_targets(
            droid_probe_config.FLEET_PATH
        )
    ]
    assert receipt["qualified_targets"] == expected
    assert len(expected) == 17
    receipt_schema.validate_receipt_components(receipt)
    partial = [entry for entry in expected if entry["model"] != "gpt-6.1-sol"]
    for broken in (
        None,
        [],
        [{"model": "gpt-6.1-sol"}],
        [{"model": "", "effort": "low"}],
        [{"model": "unknown-model", "effort": "low"}],
        expected[:1] + expected[:1],
        partial,
    ):
        tampered = dict(receipt, qualified_targets=broken)
        with pytest.raises(ValueError, match="qualified_targets"):
            receipt_schema.validate_receipt_components(tampered)

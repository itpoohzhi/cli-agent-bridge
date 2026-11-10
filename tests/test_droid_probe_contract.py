"""Негативные L1-оракулы квалификации образа, без процессов и таймеров."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from tests.test_droid_integration import FakeRpc, fake_probes as fake_probes
from tools import droid_image
from tools.droid_probe_config import ProbeTarget

EXPECTED: dict[str, object] = {
    "modelId": "test",
    "reasoningEffort": "high",
    "autonomyLevel": "high",
}


@pytest.mark.parametrize(
    "result",
    [
        {"sessionId": "", "settings": EXPECTED},
        {"sessionId": 1, "settings": EXPECTED},
        {"sessionId": "sid", "settings": []},
    ],
)
def test_initialize_requires_nonempty_sid_and_settings(result: dict) -> None:
    rpc = SimpleNamespace(call=lambda *_: (result, []))
    with pytest.raises(droid_image.ProbeError, match="initialize_session"):
        droid_image._initialize_probe(
            cast(droid_image._Rpc, cast(object, rpc)), Path("/fake"), EXPECTED
        )


@pytest.mark.parametrize(
    "listed", [None, [], [{}], ["tool"], [{"id": ""}], [{"id": 1}]]
)
def test_tool_registry_requires_nonempty_string_ids(listed: object) -> None:
    rpc = SimpleNamespace(call=lambda *_: ({"tools": listed}, []))
    with pytest.raises(droid_image.ProbeError, match="list_tools"):
        droid_image._probe_tool_ids(cast(droid_image._Rpc, cast(object, rpc)))


def test_missing_inline_readback_waits_for_notification() -> None:
    calls = []
    rpc = SimpleNamespace(
        call=lambda *args: ({}, []),
        wait_settings=lambda: (
            calls.append("wait") or {"disabledToolIds": ["Read"], **EXPECTED}
        ),
    )
    confirmed = droid_image._disable_probe_tools(
        cast(droid_image._Rpc, cast(object, rpc)), {"Read"}, EXPECTED
    )
    assert calls == ["wait"]
    assert confirmed == {"modelId", "reasoningEffort", "autonomyLevel"}


def test_different_model_protocols_reject_qualification(
    monkeypatch: pytest.MonkeyPatch,
    fake_probes: type[FakeRpc],
    tmp_path: Path,
) -> None:
    def rpc(image: Path, cwd: Path, home: Path) -> FakeRpc:
        instance = fake_probes(image, cwd, home)
        instance.protocol = (
            "primary" if len(fake_probes.instances) <= 2 else "different"
        )
        return instance

    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", "gpt-6.1-sol")
    monkeypatch.setattr(droid_image, "_Rpc", rpc)
    with pytest.raises(droid_image.ProbeError, match="разные factoryProtocolVersion"):
        droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert all(instance.closed for instance in fake_probes.instances)


@pytest.mark.parametrize(
    ("extra", "model", "effort"),
    [
        ("gpt-6.1-sol:medium", "gpt-6.1-sol", "medium"),
        ("future-model:low", "future-model", "low"),
    ],
)
def test_configured_probe_efforts_are_retained(
    monkeypatch: pytest.MonkeyPatch, extra: str, model: str, effort: str
) -> None:
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", extra)
    assert droid_image._probe_models()[model] == effort


def test_invalid_configured_probe_effort_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", "gpt-6.1-sol:off")
    with pytest.raises(droid_image.ProbeError, match="недопустимый effort"):
        droid_image._probe_models()


def test_empty_droid_fleet_cannot_be_qualified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fleet = tmp_path / "fleet.json"
    fleet.write_text('{"models": []}', encoding="utf-8")
    monkeypatch.setenv("DROID_DSH_BRIDGE_FLEET", str(fleet))
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", "")
    with pytest.raises(droid_image.ProbeError, match="отсутствуют модели droid"):
        droid_image._probe_models()


def test_probe_rejects_disk_profile_tampering(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        droid_image, "load_droid_probe_targets", lambda *_: (ProbeTarget("one", "off"),)
    )

    def probe(
        image: Path, cwd: Path, home: Path, mid: str, effort: str
    ) -> tuple[str, set[str], set[str]]:
        (home / ".factory/settings.json").write_text("{}")
        return "protocol", {"tool"}, set()

    monkeypatch.setattr(droid_image, "_probe_model", probe)
    with pytest.raises(droid_image.ProbeError, match="settings.json"):
        droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert not (tmp_path / "runtime/probe-home").exists()


def test_probe_timeout_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DROID_PROBE_TIMEOUT_S", "2.75")
    assert droid_image._get_probe_timeout_s() == 2.75
    monkeypatch.setenv("DROID_PROBE_TIMEOUT_S", "")
    assert droid_image._get_probe_timeout_s() == 30.0

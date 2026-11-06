"""Регрессии замечаний Совета Cycle 2 на реальных границах шлюза."""

from __future__ import annotations

import json
from typing import Any
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest

import server
from tests.test_request_attribution import route as route
from tools import droid_image, droid_probe_config, receipt_schema


@pytest.fixture(autouse=True)
def available_test_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server.BACKENDS.get("droid"), "preflight", lambda: (True, ""))


@pytest.mark.parametrize("autonomy", [None, "", " ", "off", "low", "medium"])
def test_safe_autonomy_at_http_boundary(
    route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, autonomy: str | None
) -> None:
    monkeypatch.delenv("DROID_DEFAULT_AUTONOMY", raising=False)
    monkeypatch.delenv("DROID_ALLOW_HIGH_AUTONOMY", raising=False)
    monkeypatch.setattr(server.Handler, "_serve_json", Mock())
    monkeypatch.setattr(server.Handler, "_prompt_guard", lambda *_: (0, "-", 0))
    monkeypatch.setattr(server.Handler, "_context_gate", lambda _, req, *a: (req, None))
    monkeypatch.setattr(server, "_is_detached_enabled", lambda: False)
    h = route(
        {
            "model": "deepseek-v4.1-flash",
            "autonomy": autonomy,
            "messages": [{"role": "user", "content": "hello"}],
        }
    )
    ctx = h._serve_json.call_args.args[0]
    assert ctx["autonomy"] == (
        autonomy.strip() if autonomy and autonomy.strip() else "off"
    )
    assert ctx["autonomy_source"] == (
        "request" if autonomy and autonomy.strip() else "default"
    )
    assert ctx["effort"] == "off"


@pytest.mark.parametrize("permission", [None, "0", "false", "garbage"])
def test_high_autonomy_is_rejected_before_spawn(
    route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, permission: str | None
) -> None:
    if permission is None:
        monkeypatch.delenv("DROID_ALLOW_HIGH_AUTONOMY", raising=False)
    else:
        monkeypatch.setenv("DROID_ALLOW_HIGH_AUTONOMY", permission)
    spawn = Mock(side_effect=AssertionError("Процесс не должен запускаться"))
    monkeypatch.setattr(server.subprocess, "Popen", spawn)
    h = route({"model": "deepseek-v4.1-flash", "autonomy": "high"})
    assert h._send.call_args.args[0] == 400
    assert h._send.call_args.args[1]["error"]["type"] in {
        "autonomy_forbidden",
        "unsupported_autonomy",
    }
    spawn.assert_not_called()


@pytest.mark.parametrize(
    "default,allow,want",
    [
        ("garbage", "", "off"),
        ("high", "", "off"),
        ("high", "1", "high"),
        ("low", "", "low"),
        (" medium ", "", "medium"),
        ("off", "", "off"),
    ],
)
def test_configured_autonomy_default(
    monkeypatch: pytest.MonkeyPatch, default: str, allow: str, want: str
) -> None:
    monkeypatch.setenv("DROID_DEFAULT_AUTONOMY", default)
    monkeypatch.setenv("DROID_ALLOW_HIGH_AUTONOMY", allow)
    assert server._default_autonomy() == want


@pytest.mark.parametrize(
    "sid", ["panel-judge-k1", "JUDGE-k1", "seat-k1", "PANEL-JUDGE-K1"]
)
def test_judges_cannot_spawn_droid(
    route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, sid: str
) -> None:
    monkeypatch.delenv("DROID_DENY_SUBAGENT_PREFIXES", raising=False)
    spawn = Mock(side_effect=AssertionError("Процесс судьи не должен запускаться"))
    monkeypatch.setattr(server.subprocess, "Popen", spawn)
    h = route({"model": "deepseek-v4.1-flash"}, {"x-sUbAgEnT-iD": sid})
    assert h._send.call_args.args[0] == 403
    assert h._send.call_args.args[1]["error"]["type"] == "droid_forbidden_for_role"
    spawn.assert_not_called()


def test_custom_judge_prefixes(
    route: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DROID_DENY_SUBAGENT_PREFIXES", " custom-, other- ")
    h = route({"model": "deepseek-v4.1-flash"}, {"X-Subagent-Id": "CUSTOM-1"})
    assert h._send.call_args.args[0] == 403


@pytest.mark.parametrize(
    "qualified",
    [
        None,
        [],
        ["tool"],
        "tool",
        1,
        {},
        {"model": "tool"},
        {"model": [1]},
        {"model": ["evil"]},
    ],
)
def test_receipt_qualified_models_strict_validation(qualified: object) -> None:
    with pytest.raises(ValueError, match="qualified_models"):
        receipt_schema.validate_qualified_models(qualified, ["tool"])


def test_qualified_models_are_in_policy_fingerprint() -> None:
    a = {"a": ["tool"], "b": ["tool", "second"]}
    b = {"a": ["tool", "second"], "b": ["tool"]}
    assert receipt_schema.tools_policy_digest(
        ["tool", "second"], a
    ) != receipt_schema.tools_policy_digest(["tool", "second"], b)
    assert receipt_schema.tools_policy_digest(
        ["tool", "second"], a
    ) == receipt_schema.tools_policy_digest(
        ["second", "tool"], {"b": ["second", "tool"], "a": ["tool"]}
    )


@pytest.mark.parametrize("qualified", [None, [], ["tool"], "tool", 1])
def test_invalid_qualified_models_raise_rpc_error(
    monkeypatch: pytest.MonkeyPatch, qualified: object
) -> None:
    monkeypatch.setattr(server, "RECEIPT_REQUIRED", True)
    monkeypatch.setattr(
        server, "_load_receipt", lambda: ("", {"qualified_models": qualified})
    )
    run = object.__new__(server.Run)
    run.plan = {"settings": ("model", "high", "off")}
    with pytest.raises(
        server.RpcError,
        match="receipt missing or invalid qualified_models, re-run droid_image.py",
    ):
        run._check_tools_policy(["tool"])


@pytest.mark.parametrize("extra", ["future:bogus", " :low", "future:nan"])
def test_extra_model_invalid_effort_or_id(
    monkeypatch: pytest.MonkeyPatch, extra: str
) -> None:
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", extra)
    with pytest.raises(droid_image.ProbeError):
        droid_probe_config.probe_models()


def test_extra_model_strips_spaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", " future : low ")
    assert droid_probe_config.probe_models()["future"] == "low"


def test_probe_uses_enabled_models_and_fleet_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fleet = tmp_path / "fleet.json"
    fleet.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "enabled",
                        "backend": "droid",
                        "efforts": ["off", "high"],
                        "default_effort": "high",
                    },
                    {
                        "id": "disabled",
                        "backend": "droid",
                        "enabled": False,
                        "efforts": ["high"],
                        "default_effort": "high",
                    },
                ]
            }
        )
    )
    monkeypatch.setenv("DROID_DSH_BRIDGE_FLEET", str(fleet))
    monkeypatch.delenv("DROID_EXTRA_PROBE_MODELS", raising=False)
    assert droid_probe_config.probe_models() == {"enabled": "high"}


@pytest.mark.parametrize("data", ["{", "{}", '{"models": [{"backend":"droid"}]}'])
def test_invalid_probe_fleet_is_probe_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: str
) -> None:
    fleet = tmp_path / "fleet.json"
    fleet.write_text(data)
    monkeypatch.setenv("DROID_DSH_BRIDGE_FLEET", str(fleet))
    with pytest.raises(droid_image.ProbeError):
        droid_probe_config.probe_models()


@pytest.mark.parametrize("value", ["garbage", "nan", "inf", "-inf", "0", "-1"])
def test_probe_timeout_validation_at_runtime(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DROID_PROBE_TIMEOUT_S", value)
    with pytest.raises(droid_image.ProbeError, match="DROID_PROBE_TIMEOUT_S"):
        droid_image._get_probe_timeout_s()


def test_probe_disk_profile_cleanup_and_per_model_readback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        droid_image, "_probe_models", lambda: {"one": "off", "two": "high"}
    )

    def probe(
        image: Path, cwd: Path, home: Path, mid: str, effort: str
    ) -> tuple[str, set[str], set[str]]:
        assert not (cwd / "stale").exists()
        settings = home / ".factory/settings.json"
        assert json.loads(settings.read_text()) == receipt_schema.SETTINGS_PROFILE
        (cwd / "stale").write_text("stale")
        return (
            "protocol",
            {"tool"},
            (
                {"interactionMode"}
                if mid == "one"
                else set(receipt_schema.SETTINGS_PROFILE)
            ),
        )

    monkeypatch.setattr(droid_image, "_probe_model", probe)
    facts = droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert facts["not_confirmed_readback_by_model"] == {
        "one": ["autoRejectPermissionRequests", "disableBuiltinSkills"],
        "two": [],
    }
    assert not (tmp_path / "runtime/probe-home").exists()
    assert not (tmp_path / "runtime/probe-cwd").exists()

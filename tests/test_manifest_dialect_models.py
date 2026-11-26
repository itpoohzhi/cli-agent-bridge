"""REQ-004/REQ-005 / W3: диалект по реальному fleet.json (`backends.<id>.params`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import http_post_dispatch as dispatch  # noqa: E402
from core.effort_errors import EffortValidationError  # noqa: E402
from core.http_post_routing import PreparedPostBody  # noqa: E402
from core.passthrough_autonomy import PassthroughOptions, prepare_passthrough_request  # noqa: E402

FLEET = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
MODELS = {m["id"]: m for m in FLEET["models"]}
THINK_ON = {"type": "enabled", "budget_tokens": 1024}
THINK_OFF = {"type": "disabled"}


@pytest.fixture(autouse=True)
def _isolated_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv("BRIDGE_MANIFEST_PARAMS_NORMALIZE_ENABLED", raising=False)


def _serve(model_id: str, backend: str, request: dict[str, Any], alias_effort: str | None = None, headers: Any = None) -> Any:
    """Результат `_passthrough` на реальных fleet-записях: args обслуживания либо `("sent", args)`."""
    served: list[Any] = []
    host = SimpleNamespace(
        passthrough_autonomy_validation_enabled=lambda default: False, flag_enabled=lambda name: False,
        FLAG_EFFORT_CATALOG="BRIDGE_EFFORT_CATALOG_ENABLED", EffortValidationError=EffortValidationError,
        PassthroughOptions=PassthroughOptions, prepare_passthrough_request=prepare_passthrough_request,
        describe_clamp=lambda *a: "", _log=lambda m: None, _LOG_EFFORT_MAX=32, json=json,
    )
    handler = SimpleNamespace(
        headers=headers or {}, _send=lambda *a, **k: served.append(("sent", (*a, k.get("extra_headers")))), _trace_log_fields=lambda: "",
        _serve_resilient=lambda backend_id, fn: served.append(fn.args), _serve_passthrough=lambda *a, **k: None,
    )
    model = {**MODELS[model_id], "backend": backend}
    full = {"model": model_id, **request}
    route = SimpleNamespace(
        host=host, handler=handler, ingress=SimpleNamespace(hub_auth_ok=True), raw_model=model_id, model_id=model_id,
        alias=("alias", alias_effort) if alias_effort else None, alias_effort=alias_effort, request=full, model=model,
        reject=lambda *a: False,
    )
    adapter = SimpleNamespace(id=backend, config=FLEET["backends"][backend])
    dispatch._passthrough(route, adapter, PreparedPostBody(raw=json.dumps(full).encode(), request=full))
    assert len(served) == 1, served
    return served[0]


def _wire(model_id: str, backend: str, request: dict[str, Any], alias_effort: str | None = None) -> dict[str, Any]:
    """Тело, ушедшее бы в апстрим."""
    served = _serve(model_id, backend, request, alias_effort)
    assert served[0] != "sent", served
    return served[2]


def test_fleet_dialects_are_compiled_for_runtime() -> None:
    for backend in ("neuralwatt", "opencode-go", "opencode-go-claude"):
        assert FLEET["backends"][backend]["params"]["effort_field"] in ("reasoning_effort", "none")


@pytest.mark.parametrize("extra", [{}, {"thinking": THINK_ON, "max_tokens": 4096}])
def test_haiku_on_opencode_go_claude_gets_reasoning_effort_without_thinking(extra: dict[str, Any]) -> None:
    body = _wire("claude-haiku-5-5", "opencode-go-claude", {"reasoning_effort": "low", **extra})
    assert body["reasoning_effort"] == "low"
    assert "thinking" not in body


def test_haiku_alias_low_gets_reasoning_effort_without_thinking() -> None:
    body = _wire("claude-haiku-5-5", "opencode-go-claude", {"thinking": THINK_ON, "max_tokens": 4096}, alias_effort="low")
    assert body["reasoning_effort"] == "low" and "thinking" not in body


def test_haiku_quorum_with_explicit_thinking_is_degraded_not_silently_stripped() -> None:
    request = {"reasoning_effort": "low", "thinking": THINK_ON, "max_tokens": 4096}
    kind, args = _serve("claude-haiku-5-5", "opencode-go-claude", request, headers={"X-Subagent-Id": "judge-1"})
    assert kind == "sent" and args[0] == 422
    assert args[1]["error"] == {"type": "param_degraded", "param": "thinking", "model": "claude-haiku-5-5"}
    assert args[2] == {"X-Bridge-Degraded": "thinking"}


@pytest.mark.parametrize("request_off", [{"reasoning_effort": "off"}, {"thinking": THINK_OFF}], ids=["effort-off", "thinking-disabled"])
def test_deepseek_off_on_opencode_go_gets_thinking_disabled(request_off: dict[str, Any]) -> None:
    body = _wire("deepseek-v4.1-flash", "opencode-go", request_off)
    assert body["thinking"] == THINK_OFF
    assert "reasoning_effort" not in body


@pytest.mark.parametrize("request_off", [{"reasoning_effort": "off"}, {"thinking": THINK_OFF}], ids=["effort-off", "thinking-disabled"])
def test_deepseek_off_on_neuralwatt_gets_reasoning_effort_none(request_off: dict[str, Any]) -> None:
    body = _wire("deepseek-v4.1-flash", "neuralwatt", request_off)
    assert body["reasoning_effort"] == "none"
    assert "thinking" not in body


def test_deepseek_nonoff_effort_is_kept_on_both_dialects() -> None:
    assert _wire("deepseek-v4.1-flash", "neuralwatt", {"reasoning_effort": "high"})["reasoning_effort"] == "high"
    assert _wire("deepseek-v4.1-flash", "opencode-go", {"reasoning_effort": "high"})["reasoning_effort"] == "high"


def test_rollback_flag_restores_legacy_wire_for_haiku(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_MANIFEST_PARAMS_NORMALIZE_ENABLED", "false")
    body = _wire("claude-haiku-5-5", "opencode-go-claude", {"reasoning_effort": "low", "thinking": THINK_ON, "max_tokens": 4096})
    assert body["thinking"]["type"] == "enabled"

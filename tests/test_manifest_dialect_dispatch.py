"""REQ-004 / W2: декларативный диспетчер диалекта (`backends.<id>.params`) и откат на legacy."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import http_post_dispatch as dispatch  # noqa: E402
from core import manifest_dialect_dispatch as mdd  # noqa: E402
from core import param_adapter  # noqa: E402
from core import passthrough_effort_map as pem  # noqa: E402
from core.backend_params import validate_backend_params  # noqa: E402
from core.effort_errors import EffortValidationError  # noqa: E402
from core.http_post_routing import PreparedPostBody  # noqa: E402
from core.logical_effort import canonicalize_logical_effort  # noqa: E402
from core.passthrough_autonomy import PassthroughOptions, prepare_passthrough_request  # noqa: E402

FLAG = "BRIDGE_MANIFEST_PARAMS_NORMALIZE_ENABLED"
NW = {"effort_field": "reasoning_effort", "effort_map": {"off": {"reasoning_effort": "none"}}, "strip_always": ["thinking"]}
GO = {"effort_field": "none", "effort_map": {"off": {"thinking": {"type": "disabled"}}}, "strip_always": []}
CLAUDE = {"effort_field": "reasoning_effort", "effort_map": {}, "adaptive_whitelist": ["reasoning_effort"], "strip_always": ["thinking"]}
THINK_ON = {"type": "enabled", "budget_tokens": 1024}
QUORUM = {"X-Subagent-Id": "judge-1"}


@pytest.fixture(autouse=True)
def _isolated_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv(FLAG, raising=False)


def _adapter(params: dict[str, Any] | None, adapter_id: str = "x", **config: Any) -> Any:
    return SimpleNamespace(id=adapter_id, config={**config, **({"params": params} if params is not None else {})})


def _route(request: dict[str, Any], headers: Any = None, backend: str = "x", alias_effort: str | None = None) -> Any:
    sent: list[tuple[int, dict[str, Any], dict[str, str]]] = []
    handler = SimpleNamespace(_send=lambda code, payload, extra_headers=None: sent.append((code, payload, extra_headers or {})))
    if headers is not None:
        handler.headers = headers
    return SimpleNamespace(model={"backend": backend}, request=request, alias_effort=alias_effort, model_id="m", handler=handler, sent=sent)


def _run(request: dict[str, Any], adapter: Any, headers: Any = None, backend: str = "x") -> dict[str, Any]:
    route = _route(request, headers, backend)
    return mdd.apply_passthrough_transforms(dict(request), route, SimpleNamespace(request=request), adapter)


def _legacy_reference(prepared: dict[str, Any], route: Any, body: Any, adapter: Any) -> dict[str, Any]:
    """Прежнее тело `http_post_dispatch._apply_passthrough_transforms` дословно."""
    backend_id = str(route.model.get("backend") or "")
    out = pem.apply_prepared_off_patch(prepared, body.request, route.request, adapter, backend_id)
    if pem.drops_thinking_route(adapter, backend_id):
        out = pem.drop_thinking_keep_effort(out)
    return param_adapter.clamp_thinking_budget(out)


def test_canonicalize_thinking_disabled_and_spellings() -> None:
    assert canonicalize_logical_effort({"thinking": {"type": "Disabled"}}) == "off"
    assert canonicalize_logical_effort({"reasoning_effort": "NONE"}) == "off"
    assert canonicalize_logical_effort({"reasoning_effort": "High", "thinking": {"type": "disabled"}}) == "high"
    assert canonicalize_logical_effort({}, None, alias_effort="Low") == "low"
    assert canonicalize_logical_effort({}, model={"default_effort": "high"}) == "high"
    assert canonicalize_logical_effort({"thinking": THINK_ON}, "bad", None) == ""


def test_thinking_disabled_becomes_off_even_with_strip_always_thinking() -> None:
    out = _run({"thinking": {"type": "disabled"}, "max_tokens": 64}, _adapter(NW))
    assert out == {"reasoning_effort": "none", "max_tokens": 64}


def test_explicit_off_effort_uses_effort_map_patch() -> None:
    assert _run({"reasoning_effort": "off"}, _adapter(NW)) == {"reasoning_effort": "none"}
    assert _run({"reasoning_effort": "off"}, _adapter(GO)) == {"thinking": {"type": "disabled"}}
    assert _run({"thinking": {"type": "disabled"}}, _adapter(GO)) == {"thinking": {"type": "disabled"}}


@pytest.mark.parametrize("value", ["false", "0", "FALSE"])
def test_rollback_flag_is_byte_identical_to_legacy(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(FLAG, value)
    assert mdd.manifest_params_enabled() is False
    cases = [
        (_adapter(NW, "neuralwatt"), "neuralwatt", {"reasoning_effort": "off", "thinking": THINK_ON, "max_tokens": 4096}),
        (_adapter(GO, "opencode-go"), "opencode-go", {"thinking": {"type": "disabled"}, "temperature": 9}),
        (_adapter(CLAUDE, "opencode-go-claude", base_url="http://127.0.0.1:10830/go/v1"), "opencode-go-claude", {"reasoning_effort": "low", "thinking": THINK_ON, "max_tokens": 4096}),
        (_adapter(None, "other"), "other", {"temperature": 7, "stop": ["a"] * 9, "thinking": THINK_ON, "max_tokens": 2048}),
    ]
    for adapter, backend, request in cases:
        route, body = _route(request, QUORUM, backend), SimpleNamespace(request=request)
        got = mdd.apply_passthrough_transforms(dict(request), route, body, adapter)
        want = _legacy_reference(dict(request), route, body, adapter)
        assert json.dumps(got, sort_keys=True).encode() == json.dumps(want, sort_keys=True).encode()


def test_flag_default_is_on_and_dialect_differs_from_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FLAG, raising=False)
    assert mdd.manifest_params_enabled() is True
    request = {"reasoning_effort": "low", "thinking": THINK_ON, "max_tokens": 4096}
    assert _run(request, _adapter(CLAUDE)) == {"reasoning_effort": "low", "max_tokens": 4096}
    monkeypatch.setenv(FLAG, "0")
    assert _run(request, _adapter(CLAUDE))["thinking"]["type"] == "enabled"


def test_missing_or_invalid_params_fall_back_to_legacy() -> None:
    request = {"temperature": 7, "thinking": THINK_ON, "max_tokens": 4096}
    for adapter in (_adapter(None), _adapter({}), _adapter({"effort_field": "bogus"}), SimpleNamespace(id="x")):
        route, body = _route(request), SimpleNamespace(request=request)
        assert mdd.apply_passthrough_transforms(dict(request), route, body, adapter) == _legacy_reference(dict(request), route, body, adapter)


def test_quorum_call_raises_param_degraded_for_stripped_thinking() -> None:
    request = {"reasoning_effort": "low", "thinking": THINK_ON}
    for headers in (QUORUM, {"X-Review-Profile": "zero-canon"}):
        with pytest.raises(mdd.ParamDegradedError) as caught:
            _run(request, _adapter(CLAUDE), headers)
        assert (caught.value.param, caught.value.model_id) == ("thinking", "m")


def test_quorum_thinking_disabled_translated_is_not_degradation() -> None:
    assert _run({"thinking": {"type": "disabled"}}, _adapter(NW), QUORUM) == {"reasoning_effort": "none"}


def test_non_quorum_strips_silently_and_ignores_missing_headers() -> None:
    request = {"reasoning_effort": "low", "thinking": THINK_ON}
    assert _run(request, _adapter(CLAUDE), {"X-Subagent-Id": "worker-1"}) == {"reasoning_effort": "low"}
    assert _run(request, _adapter(CLAUDE), None) == {"reasoning_effort": "low"}  # у handler нет headers
    assert _run({"reasoning_effort": "low"}, _adapter(CLAUDE), QUORUM) == {"reasoning_effort": "low"}  # thinking не передан


def test_effort_kept_when_field_none_without_map_entry() -> None:
    assert _run({"reasoning_effort": "high", "max_tokens": 8}, _adapter(GO)) == {"reasoning_effort": "high", "max_tokens": 8}
    assert _run({"effort": "max"}, _adapter(GO)) == {"effort": "max"}
    stripped = {**GO, "strip_always": ["reasoning_effort"]}
    assert _run({"reasoning_effort": "high"}, _adapter(stripped)) == {}


def test_clamp_thinking_budget_only_for_enabled_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(param_adapter, "clamp_thinking_budget", lambda body: calls.append(dict(body)) or dict(body))
    out = _run({"reasoning_effort": "low", "thinking": THINK_ON}, _adapter(CLAUDE))
    assert "thinking" not in out and calls == []  # снятый thinking не восстанавливается и не клампится
    _run({"thinking": {"type": "disabled"}, "max_tokens": 9}, _adapter({**GO, "effort_map": {}}))
    assert calls == []
    out = _run({"thinking": THINK_ON, "max_tokens": 4096}, _adapter({"effort_field": "none"}))
    assert len(calls) == 1 and out["thinking"] == THINK_ON


def test_handle_param_degraded_sends_422_with_header() -> None:
    route = _route({})
    mdd.handle_param_degraded(route, mdd.ParamDegradedError("thinking", "m"))
    code, payload, headers = route.sent[0]
    assert code == 422 and payload["error"] == {"type": "param_degraded", "param": "thinking", "model": "m"}
    assert headers == {"X-Bridge-Degraded": "thinking"}


def _passthrough_route(request: dict[str, Any], headers: Any, adapter: Any) -> tuple[Any, list[Any]]:
    served: list[Any] = []
    host = SimpleNamespace(
        passthrough_autonomy_validation_enabled=lambda default: False, flag_enabled=lambda name: False,
        FLAG_EFFORT_CATALOG="BRIDGE_EFFORT_CATALOG_ENABLED", EffortValidationError=EffortValidationError,
        PassthroughOptions=PassthroughOptions, prepare_passthrough_request=prepare_passthrough_request,
        describe_clamp=lambda *a: "", _log=lambda m: None, _LOG_EFFORT_MAX=32, json=json,
    )
    route = _route(request, headers, backend="x")
    route.host, route.raw_model, route.alias, route.model = host, "m", None, {"backend": "x"}
    route.reject = lambda *a: False
    route.ingress = SimpleNamespace(hub_auth_ok=True)
    route.handler._serve_resilient = lambda backend, fn: served.append(fn.args)
    route.handler._serve_passthrough = lambda *a, **k: None
    route.handler._trace_log_fields = lambda: ""
    host._log = lambda m: None
    return route, served


def test_passthrough_dispatch_answers_422_on_quorum_degrade_and_serves_otherwise() -> None:
    request = {"model": "m", "reasoning_effort": "low", "thinking": THINK_ON}
    body = PreparedPostBody(raw=json.dumps(request).encode(), request=request)
    route, served = _passthrough_route(request, QUORUM, _adapter(CLAUDE))
    dispatch._passthrough(route, _adapter(CLAUDE), body)
    assert [s[0] for s in route.sent] == [422] and served == []
    route, served = _passthrough_route(request, {"X-Subagent-Id": "worker-1"}, _adapter(CLAUDE))
    dispatch._passthrough(route, _adapter(CLAUDE), body)
    assert route.sent == [] and "thinking" not in served[0][2]


def test_f012_quorum_thinking_none_is_not_degradation() -> None:
    out = _run({"reasoning_effort": "low", "thinking": None}, _adapter(CLAUDE), QUORUM)
    assert out == {"reasoning_effort": "low"}


def test_f012_quorum_disabled_in_request_but_absent_in_prepared_translates_off() -> None:
    request = {"thinking": {"type": "disabled"}, "max_tokens": 8}
    route = _route(request, QUORUM, "neuralwatt")
    out = mdd.apply_passthrough_transforms({"max_tokens": 8}, route, SimpleNamespace(request=request), _adapter(NW, "neuralwatt"))
    assert out == {"reasoning_effort": "none", "max_tokens": 8}


def test_f011_manifest_strip_always_degrades_on_quorum_without_hardcode(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("hardcoded drops_thinking_route must not run in manifest branch")

    monkeypatch.setattr(pem, "drops_thinking_route", _boom)
    monkeypatch.setattr(pem, "drop_thinking_keep_effort", _boom)
    request = {"reasoning_effort": "low", "thinking": {"type": "enabled", "budget_tokens": 512}}
    adapter = _adapter(NW, "neuralwatt")
    route = _route(request, QUORUM, "neuralwatt")
    with pytest.raises(mdd.ParamDegradedError) as caught:
        mdd.apply_passthrough_transforms(dict(request), route, SimpleNamespace(request=request), adapter)
    mdd.handle_param_degraded(route, caught.value)
    code, payload, headers = route.sent[0]
    assert code == 422 and payload["error"]["param"] == "thinking" and headers == {"X-Bridge-Degraded": "thinking"}
    assert _run(request, adapter, {"X-Subagent-Id": "worker-1"}, "neuralwatt") == {"reasoning_effort": "low"}


def test_f002_quorum_enabled_thinking_not_masked_by_disabled_prepared() -> None:
    request = {"thinking": {"type": "enabled", "budget_tokens": 512}}
    route = _route(request, QUORUM, "neuralwatt", alias_effort="off")
    prepared = {"thinking": {"type": "disabled"}}
    with pytest.raises(mdd.ParamDegradedError):
        mdd.apply_passthrough_transforms(prepared, route, SimpleNamespace(request=request), _adapter(NW, "neuralwatt"))


def test_f002_translate_off_drops_residual_enabled_thinking() -> None:
    adapter = _adapter({"effort_field": "reasoning_effort", "effort_map": {"off": {"reasoning_effort": "none"}}})
    request = {"thinking": {"type": "disabled"}}
    route = _route(request, QUORUM)
    prepared = {"thinking": {"type": "enabled", "budget_tokens": 2048}}
    out = mdd.apply_passthrough_transforms(prepared, route, SimpleNamespace(request=request), adapter)
    assert "thinking" not in out and out["reasoning_effort"] == "none"


def _fleet_drop_thinking_backends() -> list[tuple[str, dict[str, Any]]]:
    fleet = json.loads((Path(__file__).resolve().parent.parent / "fleet.json").read_text(encoding="utf-8"))
    found = []
    for backend_id, entry in fleet["backends"].items():
        adapter = _adapter(entry.get("params"), backend_id, **{k: v for k, v in entry.items() if k != "params"})
        if pem.drops_thinking_route(adapter, backend_id):
            found.append((backend_id, entry))
    return found


def test_fleet_parity_every_drops_thinking_backend_has_valid_manifest_params() -> None:
    backends = _fleet_drop_thinking_backends()
    assert {"neuralwatt", "neuralwatt-flex", "openai-key-2", "openai-key-3"} <= {b for b, _ in backends}
    for backend_id, entry in backends:
        params = entry.get("params")
        assert params and not validate_backend_params(params), backend_id
        assert "thinking" in params["strip_always"] and "thinking" not in params["adaptive_whitelist"], backend_id
        assert "off" in params["effort_map"], backend_id
        adapter = _adapter(params, backend_id, **{k: v for k, v in entry.items() if k != "params"})
        enabled = {"thinking": {"type": "enabled", "budget_tokens": 512}}
        with pytest.raises(mdd.ParamDegradedError):
            mdd.apply_passthrough_transforms(dict(enabled), _route(enabled, QUORUM, backend_id), SimpleNamespace(request=enabled), adapter)
        disabled = {"thinking": {"type": "disabled"}}
        out = mdd.apply_passthrough_transforms(dict(disabled), _route(disabled, QUORUM, backend_id), SimpleNamespace(request=disabled), adapter)
        assert out.get("reasoning_effort") == "none" and "thinking" not in out, backend_id

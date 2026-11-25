"""ARL Bridge Wave B3 tests: param_adapter, passthrough_effort_map, deepseek-direct, and http_post_dispatch."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from core.fleet_compiler import compile_fleet
from core.param_adapter import (
    ParamProfile, ParamProfileStore, ThinkingBudgetConfigError,
    adapted_max_tokens, apply_profile, clamp_thinking_budget,
    is_quorum_call, normalize_params, pristine_body, resolve_whitelist, strip_always,
)
from core.passthrough_effort_map import drop_thinking_keep_effort, drops_thinking_route

ROOT = Path(__file__).resolve().parents[1]


def _adapter(kind: str, backend_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        backend_kind=kind, kind=kind, provider=backend_id, id=backend_id,
        name=backend_id, base_url="", effort_field="reasoning_effort", effort_map=None, off_patch=None,
    )


def _bad_routes(model_items: object) -> list[dict[str, object]]:
    routes: list[dict[str, object]] = []
    for m in model_items:  # type: ignore[attr-defined]
        routes.extend(
            r for r in (m.get("routes") or ())
            if isinstance(r, dict) and (r.get("backend") == "deepseek-direct" or r.get("provider") == "deepseek-direct")
        )
    return routes


def test_b03_deepseek_direct_disabled_in_compiler() -> None:
    manifest = yaml.safe_load((ROOT / "providers.d" / "deepseek-direct.yaml").read_text(encoding="utf-8"))
    fleet = compile_fleet()
    backends = fleet.get("backends", {})
    models_raw = fleet.get("models") or ()
    model_items = models_raw.values() if isinstance(models_raw, dict) else models_raw
    dd_bad = isinstance(backends, dict) and "deepseek-direct" in backends and backends["deepseek-direct"].get("enabled") is not False
    assert (manifest["enabled"], manifest["priority"], manifest["routing"]["weight"], dd_bad, _bad_routes(model_items)) == (False, 20, 0, False, [])


def test_b06_param_adapter_clamp_and_quorum() -> None:
    assert is_quorum_call(subagent_id=None, review_profile="Zero-Canon") is True
    assert is_quorum_call(subagent_id="custom-1", review_profile=None, prefixes=("custom",)) is True
    assert "reasoning_effort" in resolve_whitelist()

    src = {"model": "m1", "max_tokens": 256, "temperature": 0.7, "thinking": {"type": "enabled", "budget_tokens": 512}}
    clamped = clamp_thinking_budget(src)
    assert clamped["thinking"]["budget_tokens"] == 255
    assert "budget_tokens" not in clamp_thinking_budget({"thinking": {"type": "enabled", "budget_tokens": True}}).get("thinking", {})
    assert "thinking" not in clamp_thinking_budget({"thinking": {"type": "enabled", "budget_tokens": 512}})
    assert clamp_thinking_budget({"thinking": {"type": "enabled", "budget_tokens": 128}, "max_tokens": 256})["thinking"]["budget_tokens"] == 128
    with pytest.raises(ThinkingBudgetConfigError):
        clamp_thinking_budget({"max_tokens": 512, "thinking": {"type": "enabled", "budget_tokens": 1024}})
    tiny = clamp_thinking_budget({"max_tokens": 2, "thinking": {"type": "enabled", "budget_tokens": 512}})
    assert ("thinking" not in tiny, adapted_max_tokens({"max_completion_tokens": 300})) == (True, 300)


def test_b06_param_profile_and_effort_map(tmp_path: Path) -> None:
    src = {"model": "m1", "max_tokens": 256, "temperature": 0.7, "thinking": {"type": "enabled", "budget_tokens": 512}}
    pfile = tmp_path / "profiles.json"
    pfile.write_text(json.dumps({"version": 1, "profiles": {"k": {"bad": "str", "ok": {"action": "drop", "expires_at": 9e18}}}}), encoding="utf-8")
    store = ParamProfileStore(path=pfile, clock=lambda: 100.0)
    prof = store.record_drop("p", "m", "fp", "temperature")
    assert (prof.drops("temperature"), pfile.read_text(encoding="utf-8").index('"profiles"') < pfile.read_text(encoding="utf-8").index('"version"')) == (True, True)
    assert apply_profile(src, None) == pristine_body(src)
    assert strip_always({"a": [1], "thinking": 2}, ("thinking",)) == {"a": [1]}
    assert apply_profile(src, ParamProfile(("temperature",)))["max_tokens"] == 256

    nw = _adapter("openai", "neuralwatt")
    assert (drops_thinking_route(nw, "neuralwatt"), drops_thinking_route(_adapter("agy", "agy"), "agy")) == (True, False)
    norm = normalize_params({**src, "reasoning_effort": "low"}, effort_field="reasoning_effort")
    dropped = drop_thinking_keep_effort(norm)
    assert ("thinking" not in dropped, dropped["reasoning_effort"]) == (True, "low")


class _EffortErr(Exception):
    pass


def _passthrough_harness():
    seen: list[tuple[str, bytes, dict[str, Any]]] = []
    rejected: list[tuple[int, str]] = []
    host = SimpleNamespace(
        passthrough_autonomy_validation_enabled=lambda _d: False, flag_enabled=lambda _k: True,
        EffortValidationError=_EffortErr, json=json, _strip_passthrough_env=lambda raw, req: (raw, req),
        resolve_target_model=lambda m, c: c, _log=lambda _m: None,
    )
    handler = SimpleNamespace(
        _reject=lambda status, kind, *_a: rejected.append((status, kind)),
        _serve_resilient=lambda backend, fn: fn(),
        _serve_passthrough=lambda adapter, raw, prep, mid, **_kw: seen.append((adapter.id, raw, prep)),
        _trace_log_fields=lambda: "",
    )
    return host, handler, seen, rejected


def test_b06_passthrough_live_clamp_and_drop() -> None:
    from core import http_post_dispatch as hpd

    host, handler, seen, rejected = _passthrough_harness()

    def _call(adapter_id: str, backend: str, req: dict[str, Any]) -> None:
        raw = json.dumps(req).encode("utf-8")
        ingress = SimpleNamespace(host=host, handler=handler, raw=raw, request=req, hub_auth_ok=False)
        route = SimpleNamespace(
            ingress=ingress, host=host, handler=handler, request=req, model_id="m1",
            raw_model="m1", model_len=2, model={"backend": backend}, alias=None, alias_effort=None,
            reject=lambda s, k, _m: rejected.append((s, k)),
        )
        hpd._passthrough(route, SimpleNamespace(id=adapter_id, config={}), None)

    _call("agy", "agy", {"model": "m1", "max_tokens": 256, "thinking": {"type": "enabled", "budget_tokens": 512}})
    _call("x", "neuralwatt", {"model": "m1", "max_tokens": 256, "reasoning_effort": "low", "thinking": {"type": "enabled", "budget_tokens": 512}})
    _call("agy", "agy", {"model": "m1", "max_tokens": 512, "thinking": {"type": "enabled", "budget_tokens": 1024}})
    assert (seen[0][2]["thinking"], "thinking" not in seen[1][2], seen[1][2]["reasoning_effort"], rejected) == (
        {"type": "enabled", "budget_tokens": 255}, True, "low", [(400, "invalid_request")],
    )

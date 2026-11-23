"""Контракты manifest/compiler/артефактов, независимые от выданного ими результата."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import itertools
import json
from dataclasses import replace
from typing import Any

import pytest

from adapters import ADAPTER_KINDS
from core.backend_adapter import FleetViolation, _normalize_model
from core.fleet_compiler import canonical_json, compile_catalog, render_fleet_json
from core.fleet_explain import explain_model
from core.provider_manifest import load_schema, manifest_files, read_yaml_file, validate_manifest
from tests.test_transport_routing import ALGORITHM, CATALOG_HASH, MODEL, ROOT, ROUTES, compiled, feature_api, provider
from tests.transport_test_support import semantic_equal


def manifest_doc(routing: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "manifest_version": 1, "provider_id": "demo", "kind": "passthrough",
        "owned_by": "test", "transport": {"bridge": {"base_url": "http://127.0.0.1:9100/v1"}},
        "allow_base_url": [{"scheme": "http", "host": "127.0.0.1", "port": 9100, "path_prefix": "/v1"}],
    }
    if routing is not None:
        result["routing"] = routing
    return result


def raw_provider(pid: str) -> dict[str, Any]:
    """Читает существующие manifests; отсутствие нового слота видно как пустой контракт."""
    docs = {path.stem: read_yaml_file(path) for path in manifest_files(ROOT / "providers.d")}
    return docs.get(pid, {})


def route_model() -> dict[str, Any]:
    return dict(compiled().fleet["models"][0], routing={
        "algorithm": ALGORITHM, "enabled": True, "catalog_hash": CATALOG_HASH,
        "legacy_backend": "beta", "disabled_backend": "alpha", "routes": list(ROUTES),
    })


@pytest.mark.semantic_red("pure_compile_owner")
def test_stage_w1_b_pure_owner_hash_and_reserve_permutations() -> None:
    api = feature_api("core.catalog_routes", "pure_compile_owner")
    inputs = (provider("alpha", 1, 0), provider("beta", 3, 90), provider("reserve", 0, 0))
    for permutation in itertools.permutations(inputs):
        routing = api.compile_model_routing(permutation, "alpha")
        actual = (routing["legacy_backend"], routing["disabled_backend"], routing["catalog_hash"], [r["backend"] for r in routing["routes"]])
        semantic_equal(actual, ("beta", "alpha", CATALOG_HASH, ["alpha", "beta", "reserve"]),
                       "pure_compile_owner")


@pytest.mark.semantic_red("closed_manifest_routing")
@pytest.mark.parametrize("weight", [0, 1, 10000])
def test_stage_w2_f_manifest_accepts_weight_and_preserves_absence(weight: int) -> None:
    result = validate_manifest(manifest_doc({"weight": weight}), ADAPTER_KINDS, env={})
    semantic_equal(result.errors, (), "closed_manifest_routing")
    assert result.manifest is not None and result.manifest.routing.weight == weight
    old = validate_manifest(manifest_doc(), ADAPTER_KINDS, env={})
    assert old.ok and old.manifest is not None and old.manifest.routing.weight is None


@pytest.mark.semantic_red("closed_manifest_routing")
@pytest.mark.parametrize("routing", [
    {}, {"weight": True}, {"weight": -1}, {"weight": 10001}, {"weight": 1.5},
    {"weight": float("nan")}, {"weight": "1"}, {"weight": 1, "extra": 0}, [],
])
def test_stage_w2_f_invalid_routing_never_normalizes(routing: Any) -> None:
    result = validate_manifest(manifest_doc(routing), ADAPTER_KINDS, env={})
    semantic_equal(result.manifest is None and bool(result.errors), True,
                   "closed_manifest_routing")


@pytest.mark.semantic_red("schema_routing_weight")
def test_stage_w2_g_json_schema_closed_integer_weight() -> None:
    schema = load_schema().get("properties", {}).get("routing", {})
    weight = schema.get("properties", {}).get("weight", {})
    actual = (schema.get("type"), schema.get("additionalProperties"), schema.get("required"),
              weight.get("type"), weight.get("minimum"), weight.get("maximum"))
    semantic_equal(actual, ("object", False, ["weight"], "integer", 0, 10000), "schema_routing_weight")


@pytest.mark.semantic_red("pure_compile_owner")
def test_stage_w1_b_owner_ignores_disabled_and_direct_only_routes() -> None:
    api = feature_api("core.catalog_routes", "pure_compile_owner")
    live = (provider("alpha", 5, 20), provider("beta", 5, 10), provider("gamma", 5, 10))
    disabled = replace(provider("disabled", 10000, 0), enabled=False)
    direct = replace(provider("direct", 10000, 0), transport=replace(live[0].transport, bridge=None))
    routing = api.compile_model_routing((*live, disabled, direct), "alpha")
    semantic_equal(routing["legacy_backend"], "beta", "pure_compile_owner")
    assert [r["backend"] for r in routing["routes"]] == ["alpha", "beta", "gamma"]


@pytest.mark.semantic_red("pure_closed_weight")
def test_stage_w1_b_pure_closed_weight_parser() -> None:
    api = feature_api("core.routing_schema", "pure_closed_weight")
    for value in (0, 1, 10000):
        assert api.parse_routing({"weight": value}).weight == value
    for doc in ({}, {"weight": False}, {"weight": 10001}, {"weight": 1, "extra": 0}):
        with pytest.raises(ValueError):
            api.parse_routing(doc)
    assert api.parse_routing(None).weight is None


@pytest.mark.semantic_red("fleet_routing_validation")
def test_stage_w2_g_model_normalizer_preserves_routes() -> None:
    if importlib.util.find_spec("core.fleet_model_validation") is None:
        normalize = _normalize_model
    else:
        normalize = importlib.import_module("core.fleet_model_validation").normalize_model
    record = route_model()
    backends = {r["backend"]: {"enabled": True} for r in ROUTES}
    try:
        actual = normalize(record, MODEL, 3, backends, False)
    except FleetViolation as error:
        actual = {"rejected": error.reason}
    semantic_equal(actual.get("routing"), record["routing"], "fleet_routing_validation")


@pytest.mark.semantic_red("fleet_routing_validation")
def test_stage_w2_h_existing_normalizer_accepts_routing() -> None:
    record = route_model()
    backends = {r["backend"]: {"enabled": True} for r in ROUTES}
    try:
        actual = _normalize_model(record, MODEL, 3, backends, False)
    except FleetViolation as error:
        actual = {"rejected": error.reason}
    semantic_equal(actual.get("routing"), record["routing"], "fleet_routing_validation")


@pytest.mark.semantic_red("fleet_routing_validation")
@pytest.mark.parametrize("defect", [
    "unknown_backend", "duplicate_route", "duplicate_backend", "bool_weight",
    "negative_weight", "bool_priority", "bad_hash", "missing_key", "extra_key",
    "missing_routing_key", "extra_routing_key",
])
def test_stage_w2_h_invalid_route_rejects_whole_model(defect: str) -> None:
    record = copy.deepcopy(route_model())
    routing = record["routing"]
    route = routing["routes"][0]
    changes = {
        "unknown_backend": ("backend", "unknown"), "bool_weight": ("weight", True),
        "negative_weight": ("weight", -1), "bool_priority": ("priority", True),
    }
    if defect in changes:
        key, value = changes[defect]
        route[key] = value
    elif defect == "duplicate_route":
        routing["routes"].append(dict(route, backend="reserve"))
    elif defect == "duplicate_backend":
        routing["routes"].append(dict(route, route_id="different"))
    elif defect == "bad_hash":
        routing["catalog_hash"] = "0" * 64
    elif defect == "missing_key":
        route.pop("weight")
    elif defect == "missing_routing_key":
        routing.pop("algorithm")
    elif defect == "extra_routing_key":
        routing["surprise"] = True
    else:
        route["surprise"] = True
    with pytest.raises(FleetViolation):
        _normalize_model(record, MODEL, 3, {r["backend"]: {"enabled": True} for r in ROUTES}, False)


def owner_contract(compiler: Any, defect: str) -> None:
    result = compiled(compiler=compiler)
    model = result.fleet["models"][0]
    actual = (model["backend"], result.sidecar["models"][MODEL]["provider"])
    semantic_equal(actual, ("beta", "beta"), defect)
    assert model["routing"]["disabled_backend"] == "alpha"
    assert result.rejected == {} and result.rejected_providers == {}
    assert result.sidecar["models"][MODEL]["quorum_eligible"] is False


@pytest.mark.semantic_red("pipeline_weighted_owner")
def test_stage_w2_i_pipeline_weighted_owner_and_provenance() -> None:
    name = "core.compile_routes_pipeline"
    compiler = (importlib.import_module(name).compile_catalog if importlib.util.find_spec(name) is not None else compile_catalog)
    owner_contract(compiler, "pipeline_weighted_owner")


@pytest.mark.semantic_red("compiler_weighted_owner")
def test_stage_w2_j_compiler_owner_and_input_byte_canonicalization() -> None:
    owner_contract(compile_catalog, "compiler_weighted_owner")
    inputs = (provider("alpha", 1, 0), provider("beta", 3, 90), provider("reserve", 0, 20))
    result = compiled(inputs)
    explanation = explain_model(result.sidecar, inputs, MODEL)
    assert explanation is not None and explanation.primary == "beta"
    ranked = explanation.to_document()["candidates"]
    assert ranked[0]["provider_id"] == "beta"
    outputs = []
    for permutation in itertools.permutations(inputs):
        result = compiled(permutation)
        outputs.append((render_fleet_json(result.fleet), canonical_json(result.sidecar)))
    assert all(output == outputs[0] for output in outputs)


@pytest.mark.semantic_red("openai_slots")
@pytest.mark.parametrize("slot", [2, 3])
def test_stage_w2_n_openai_credential_slot_mapping(slot: int) -> None:
    doc = raw_provider(f"openai-key-{slot}")
    actual = (doc.get("routing"), doc.get("transport", {}).get("bridge"),
              doc.get("limits", {}).get("quota_group"), sorted(doc.get("models_overrides", {})))
    expected = ({"weight": 50}, {"base_url": "http://127.0.0.1:10830/sg-openai", "api_key_env": f"OPENAI_API_KEY_{slot}"},
                f"openai-key-{slot}", ["gpt-6.1-sol", "gpt-6.1-terra"])
    semantic_equal(actual, expected, "openai_slots")


@pytest.mark.semantic_red("deepseek_slot_and_policy")
def test_stage_w2_o_deepseek_slot_and_policy_fingerprint() -> None:
    doc = raw_provider("deepseek-direct")
    actual = (doc.get("routing"), doc.get("transport", {}).get("bridge"), sorted(doc.get("models_overrides", {})))
    semantic_equal(actual, ({"weight": 0}, {"base_url": "http://127.0.0.1:10830/sg-deepseek",
                   "api_key_env": "DEEPSEEK_API_KEY"}, ["deepseek-v4.1-flash"]), "deepseek_slot_and_policy")
    assert doc["limits"]["quota_group"] == "deepseek-direct"
    header = read_yaml_file(ROOT / "providers.d" / "_fleet.yaml")
    assert header["policy_ref"]["sha256"] == ("6fc23e304e870f0d91678a401e784692099e7414e73c904d3e3f769722d3354c")


@pytest.mark.semantic_red("native_zero_reserves")
@pytest.mark.parametrize("pid", ["codex", "droid"])
def test_stage_w2_p_native_zero_reserves_preserve_models(pid: str) -> None:
    doc = raw_provider(pid)
    semantic_equal(doc.get("routing"), {"weight": 0}, "native_zero_reserves")
    expected = {"gpt-6.1-sol", "gpt-6.1-terra"} if pid == "codex" else {
        "gpt-6.1-sol", "gpt-6.1-sol-droid", "gemini-3.8-flash", "gemini-3.8-flash-droid",
        "claude-sonnet-5-5", "claude-sonnet-5-5-droid",
    }
    assert set(doc["models_overrides"]) == expected


@pytest.mark.semantic_red("go_zen_weight_split")
def test_stage_w2_q_paid_reserve_and_free_zen_independent_catalog() -> None:
    go, zen = raw_provider("opencode-go"), raw_provider("opencode-zen")
    semantic_equal((go.get("routing"), zen.get("routing")), ({"weight": 40}, {"weight": 100}), "go_zen_weight_split")
    assert zen["transport"]["bridge"]["base_url"] == "http://127.0.0.1:9883/v1"
    assert "deepseek-v4.1-flash" in go["models_overrides"]
    assert {"deepseek-v4.1-flash-free", "big-pickle", "iceman-free"} <= set(zen["models_overrides"])


@pytest.mark.semantic_red("existing_bridge_weights")
@pytest.mark.parametrize("pid", ["claude-p", "agy"])
def test_stage_w2_r_existing_bridge_weights_and_hydrogen(pid: str) -> None:
    doc = raw_provider(pid)
    semantic_equal(doc.get("routing"), {"weight": 100}, "existing_bridge_weights")
    if pid == "agy":
        hydrogen = doc["models_overrides"]["gemini-4-hydrogen"]
        assert hydrogen["efforts"] == ["low", "medium", "high", "xhigh"]
        assert (hydrogen["context_window"], hydrogen["max_tokens"]) == (1048576, 65536)
        assert hydrogen["images"]["cli_registry"] == "implicit_supported"


@pytest.mark.semantic_red("muse_weight_without_retirement")
def test_stage_w2_s_muse_weight_preserves_five_model_contracts() -> None:
    doc = raw_provider("muse")
    semantic_equal(doc.get("routing"), {"weight": 100}, "muse_weight_without_retirement")
    assert set(doc["models_overrides"]) == {
        "muse-ember-1.0", "muse-spark-1.3", "muse-spark-1.3-contributor",
        "muse-wonder-1.0", "muse-wonder-full-1.0",
    }
    assert doc.get("enabled", True) is True


@pytest.mark.semantic_red("generated_weighted_catalog")
def test_stage_w2_t_generated_artifacts_route_owners_and_digest() -> None:
    fleet = json.loads((ROOT / "fleet.json").read_bytes())
    lock = json.loads((ROOT / "catalog.lock.json").read_bytes())
    models = {record["id"]: record for record in fleet["models"]}
    actual = {mid: models[mid].get("routing", {}).get("legacy_backend") for mid in ("gpt-6.1-sol", "gpt-6.1-terra", "deepseek-v4.1-flash")}
    semantic_equal(actual, {"gpt-6.1-sol": "openai-key-3", "gpt-6.1-terra": "openai-key-3", "deepseek-v4.1-flash": "neuralwatt"},
                   "generated_weighted_catalog")
    assert lock["fleet_sha256"] == hashlib.sha256((ROOT / "fleet.json").read_bytes()).hexdigest()
    for mid, owner in actual.items():
        assert models[mid]["backend"] == lock["models"][mid]["provider"] == owner


@pytest.mark.semantic_red("probe_weight_ranking")
def test_stage_w2_u_weighted_bridge_owner_ranking() -> None:
    from core.probe_manifest_select import select_manifest

    alpha, beta = provider("alpha", 1, 0), provider("beta", 3, 90)
    cand = select_manifest((alpha, beta), MODEL, None)
    semantic_equal(cand.manifest.provider_id if cand.manifest else None, "beta", "probe_weight_ranking")
    assert select_manifest((beta, alpha), MODEL, None).manifest == beta
    default, priority = provider("default", None, 90), provider("priority", None, 0)
    assert select_manifest((provider("reserve", 0, 0), default), MODEL, None).manifest == default
    ties = (provider("gamma", 3, 10), provider("alpha", 3, 20), provider("beta", 3, 10))
    assert select_manifest(ties, MODEL, None).manifest == ties[2]
    static = [replace(p, discovery=replace(p.discovery, static=(MODEL,))) for p in (alpha, beta)]
    assert select_manifest(static, MODEL, None, strict_ambiguous=True).problem == "provider_ambiguous"
    direct = replace(beta, transport=replace(beta.transport, bridge=None))
    assert select_manifest((default, direct, priority), MODEL, None).manifest == priority

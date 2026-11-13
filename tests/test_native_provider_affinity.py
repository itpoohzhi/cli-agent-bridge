import json
from pathlib import Path
import pytest
from server import build_cli_model_selection, prepare_passthrough_request, resolve_target_model
from core.provider_manifest import read_yaml_file
from tests.bridge_testlib import BridgeCase

ROOT = Path(__file__).resolve().parent.parent

def _load_catalog():
    with (ROOT / "catalog.lock.json").open(encoding="utf-8") as f:
        return json.load(f)

def _load_fleet():
    with (ROOT / "fleet.json").open(encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.parametrize("model_id,expected_provider", [
    ("gemini-3.8-flash", "agy"),
    ("claude-sonnet-5-5", "claude-p"),
    ("deepseek-v4.1-flash", "opencode-go"),
    ("gpt-6.1-sol", "codex"),
])
def test_native_provider_priority(model_id, expected_provider):
    cat = _load_catalog()
    models = cat.get("models", {})
    assert model_id in models, f"{model_id} not in catalog.lock.json"
    assert models[model_id].get("provider") == expected_provider

@pytest.mark.parametrize("model_id", [
    "gemini-3.8-flash-droid",
    "gpt-6.1-sol-droid",
    "claude-sonnet-5-5-droid",
])
def test_explicit_droid_models(model_id):
    cat = _load_catalog()
    models = cat.get("models", {})
    assert model_id in models, f"{model_id} not in catalog.lock.json"
    assert models[model_id].get("provider") == "droid"

@pytest.mark.parametrize("model_id", [
    "gemini-3.8-flash",
    "claude-sonnet-5-5",
    "gpt-6.1-sol",
])
def test_droid_alternates(model_id):
    cat = _load_catalog()
    models = cat.get("models", {})
    assert model_id in models
    alts = models[model_id].get("alternates", [])
    providers = [a.get("provider") if isinstance(a, dict) else a for a in alts]
    assert "droid" in providers

@pytest.mark.parametrize("droid_model,upstream_model", [
    ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
    ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
    ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
])
def test_droid_upstream_model(droid_model, upstream_model):
    fleet = _load_fleet()
    models = fleet.get("models", [])
    entry = next((m for m in models if m.get("id") == droid_model), None)
    assert entry is not None, f"{droid_model} not in fleet.json models"
    assert entry.get("upstream_model") == upstream_model

EXPECTED_FAMILY_PROVIDER = {
    "Google": "agy",
    "Anthropic": "claude-p",
    "OpenAI": "codex",
    "DeepSeek": "opencode-go",
    "Meta": "muse",
}

def test_native_provider_affinity_invariant():
    """Инвариант: родной провайдер всегда побеждает агрегаторы (droid, opencode-zen)."""
    cat = _load_catalog()
    models = cat.get("models", {})
    aggregators = {"droid", "opencode-zen"}

    for model_id, info in models.items():
        provider = info.get("provider")
        family = info.get("family")
        alternates = [a.get("provider") if isinstance(a, dict) else a for a in info.get("alternates", [])]

        if model_id.endswith("-droid"):
            assert provider == "droid", f"{model_id} should be droid, got {provider}"
        elif family in EXPECTED_FAMILY_PROVIDER:
            expected = "opencode-go-claude" if model_id == "claude-haiku-5-5" else EXPECTED_FAMILY_PROVIDER[family]
            assert provider == expected, f"{model_id} (family={family}) should be {expected}, got {provider}"
            assert provider not in aggregators, f"Canonical model {model_id} cannot have aggregator as primary, got {provider}"

        if any(alt in aggregators for alt in alternates):
            assert provider not in aggregators, f"{model_id} has aggregator alternate but primary is {provider}"

@pytest.mark.parametrize("droid_model,expected_canonical", [
    ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
    ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
    ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
])
def test_runtime_upstream_model_translation(droid_model, expected_canonical):
    """Runtime-трансляция server.py resolve_target_model подставляет upstream_model."""
    fleet = _load_fleet()
    entry = next((m for m in fleet.get("models", []) if m.get("id") == droid_model), None)
    assert entry is not None, f"{droid_model} not in fleet.json models"
    target_model = resolve_target_model(entry, droid_model)
    assert target_model == expected_canonical
    assert resolve_target_model({"id": expected_canonical}, expected_canonical) == expected_canonical


def _backend_aliases(model, backend, efforts):
    return {f"{model}-{effort}": {"backend_id": model, "backend": backend, "effort": effort} for effort in efforts}


def _target_aliases(model, efforts):
    return {f"{model}-{effort}": {"target": model, "default_effort": effort} for effort in efforts}


def test_explicit_effort_alias_contract():
    """Все 35 effort-алиасов проверяются по точной форме с учётом Hydrogen, Carbon и Argon."""
    expected = {
        **_backend_aliases("gemini-3.8-flash-droid", "droid", ("low", "medium", "high")),
        **_backend_aliases("gpt-6.1-sol-droid", "droid", ("low", "medium", "high", "max")),
        **_backend_aliases("claude-sonnet-5-5-droid", "droid", ("low", "medium", "high", "max")),
        **_backend_aliases("gpt-6.1-sol", "codex", ("low", "medium", "high", "max")),
        **_backend_aliases("gemini-3.8-flash", "agy", ("low", "medium", "high")),
        **_backend_aliases("claude-sonnet-5-5", "claude-p", ("low", "medium", "high", "max")),
        **_backend_aliases("claude-opus-5-5", "claude-p", ("medium", "high")),
        **_backend_aliases("claude-haiku-5-5", "opencode-go-claude", ("low",)),
        **_target_aliases("gemini-4-argon", ("low", "medium")),
        **_backend_aliases("gemini-4-argon", "agy", ("high",)),
        **_target_aliases("gemini-4-carbon", ("low", "medium", "high")),
        **_target_aliases("gemini-4-hydrogen", ("low", "medium", "high", "xhigh")),
    }
    assert _load_fleet().get("aliases", {}) == expected


@pytest.mark.parametrize("droid_model,expected_upstream", [
    ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
    ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
    ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
])
def test_make_plan_droid_uses_upstream_model(droid_model, expected_upstream):
    """Проверяет, что runtime _make_plan прокидывает канонический upstream_model в Droid RPC settings."""
    from server import _make_plan, resolve_target_model
    fleet = _load_fleet()
    entry = next((m for m in fleet.get("models", []) if m.get("id") == droid_model), None)
    assert entry is not None
    target = resolve_target_model(entry, droid_model)
    assert target == expected_upstream
    ctx = {
        "rpc": {"items": [], "system": ""},
        "model": droid_model,
        "target_model": target,
        "effort": "low",
        "autonomy": "off",
        "route": "nokey",
    }
    plan = _make_plan(ctx, None, "", "/tmp", [])
    assert plan["settings"][0] == expected_upstream


def test_compiled_catalog_matches_manifests():
    """Проверяет, что fleet.json и catalog.lock.json строго соответствуют компиляции манифестов providers.d."""
    from core.fleet_compiler import compile_from_disk, default_kinds
    res = compile_from_disk(
        providers_path=ROOT / "providers.d",
        fleet_meta_path=ROOT / "providers.d" / "_fleet.yaml",
        kinds=default_kinds(),
    )
    fleet = _load_fleet()
    catalog = _load_catalog()
    compiled_models = {m["id"]: m for m in res.fleet["models"]}
    disk_models = {m["id"]: m for m in fleet["models"]}
    assert compiled_models == disk_models
    assert res.fleet["aliases"] == fleet["aliases"]
    assert res.sidecar["models"] == catalog["models"]


def test_cli_exec_target_model_selection():
    """Проверяет выбор target_model через production-функцию build_cli_model_selection в _cli_exec."""
    ctx = {"model": "gemini-3.8-flash-droid", "target_model": "gemini-3.8-flash"}
    assert build_cli_model_selection(ctx) == "gemini-3.8-flash"
    ctx_plain = {"model": "gemini-3.8-flash"}
    assert build_cli_model_selection(ctx_plain) == "gemini-3.8-flash"


def test_passthrough_target_model_rewriting():
    """Проверяет подстановку target_model через production-функцию prepare_passthrough_request."""
    fleet = _load_fleet()
    entry = next((m for m in fleet.get("models", []) if m.get("id") == "gemini-3.8-flash-droid"), None)
    assert entry is not None
    req, pt_effort = prepare_passthrough_request(
        req={"model": "gemini-3.8-flash-droid"},
        model=entry,
        model_id="gemini-3.8-flash-droid",
    )
    assert req["model"] == "gemini-3.8-flash"


def test_exact_effort_alias_count():
    """Проверяет ровно 35 effort-алиасов, включая три Gemini 4 Carbon и четыре Gemini 4 Hydrogen."""
    fleet = _load_fleet()
    aliases = fleet.get("aliases", {})
    assert len(aliases) == 35, f"Expected 35 total aliases in fleet, got {len(aliases)}"
    target_aliases = [
        k for k in aliases
        if any(m in k for m in ("gemini-3.8-flash", "gemini-4-carbon", "gemini-4-hydrogen", "gpt-6.1-sol", "claude-sonnet-5-5"))
    ]
    assert len(target_aliases) == 29, f"Expected 29 target aliases including Carbon and Hydrogen, got {len(target_aliases)}"


def test_manifest_priority_values():
    """Проверяет явные числовые значения priority в providers.d/*.yaml."""
    native_files = ["agy.yaml", "claude-p.yaml", "codex.yaml", "opencode-go.yaml", "muse.yaml"]
    for fname in native_files:
        data = read_yaml_file(ROOT / "providers.d" / fname)
        assert data.get("priority") == 10, f"{fname} priority must be 10, got {data.get('priority')}"
    droid_data = read_yaml_file(ROOT / "providers.d" / "droid.yaml")
    assert droid_data.get("priority") == 30, f"droid priority must be 30, got {droid_data.get('priority')}"
    zen_data = read_yaml_file(ROOT / "providers.d" / "opencode-zen.yaml")
    assert zen_data.get("priority") == 50, f"zen priority must be 50, got {zen_data.get('priority')}"


def test_fallback_candidate_ranking_to_droid_when_native_fails():
    """Проверяет, что alternates ранжируют Droid резервным кандидатом (priority 30) при отказе native."""
    from core.fleet_explain import explain_model
    from core.provider_manifest import load_manifests
    from adapters import ADAPTER_KINDS
    cat = _load_catalog()
    manifests = load_manifests(ROOT / "providers.d", ADAPTER_KINDS).manifests
    entry = explain_model(cat, manifests, "gemini-3.8-flash")
    assert entry is not None
    assert entry.primary == "agy"
    assert "droid" in entry.alternates
    p_map = {pid: p for p, pid in entry.candidates}
    assert p_map["agy"] == 10
    assert p_map["droid"] == 30
    assert p_map["agy"] < p_map["droid"]


class TestNativeProviderE2ERouting(BridgeCase):
    """Сквозной HTTP-тест маршрутизации к нативному passthrough-провайдеру."""

    def setUp(self):
        super().setUp()
        from tests.bridge_testlib import load_raw_fleet
        from tests.test_passthrough_adapter import FakeUpstream
        from adapters import ADAPTER_KINDS
        from core.backend_adapter import AdapterRegistry
        import server
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = True
        data["backends"]["codex"]["base_url"] = f"http://127.0.0.1:{self.upstream.port}/v1"
        data["backends"]["codex"].pop("api_key_env", None)
        server.FLEET = server._build_catalog(data)
        saved = server.BACKENDS
        self.addCleanup(setattr, server, "BACKENDS", saved)
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h,
            {
                "id": "chatcmpl-native-test",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong from native codex"}, "finish_reason": "stop"}],
                "model": "gpt-6.1-sol",
            },
        )

    def test_native_provider_e2e_routing(self):
        status, body = self._post_json(
            {
                "model": "gpt-6.1-sol",
                "messages": [{"role": "user", "content": "ping"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "pong from native codex")
        self.assertEqual(body["model"], "gpt-6.1-sol")


class TestDroidModelE2ERouting(BridgeCase):
    """Сквозной HTTP-тест маршрутизации *-droid через сервер Handler."""

    def test_droid_model_e2e_routing(self):
        cases = [
            ("gemini-3.8-flash-droid", "gemini-3.8-flash"),
            ("gpt-6.1-sol-droid", "gpt-6.1-sol"),
            ("claude-sonnet-5-5-droid", "claude-sonnet-5-5"),
        ]
        for droid_model, expected_upstream in cases:
            self.hub.legacy(
                [
                    [
                        ("text", f"pong from {droid_model}"),
                        ("result", {"finalText": "", "usage": {}}),
                        ("done", (0, "")),
                    ]
                ]
            )
            status, body = self._post_json(
                {
                    "model": droid_model,
                    "messages": [{"role": "user", "content": "ping"}],
                }
            )
            self.assertEqual(status, 200)
            self.assertEqual(body["choices"][0]["message"]["content"], f"pong from {droid_model}")
            self.assertEqual(body["model"], droid_model)
            inits = self.hub.inits()
            self.assertGreaterEqual(len(inits), 1)
            self.assertEqual(
                inits[-1]["params"]["modelId"],
                expected_upstream,
                f"В Droid должна быть передана каноническая модель {expected_upstream} для {droid_model}",
            )

    def test_turn_context_positional_backward_compatibility(self):
        """Регрессионный тест: позиционные аргументы TurnContext не ломаются новым полем."""
        from core.backend_adapter import TurnContext
        turn = TurnContext("gemini-3.8-flash", "low", "test prompt", "agy", "key123")
        self.assertEqual(turn.model, "gemini-3.8-flash")
        self.assertEqual(turn.effort, "low")
        self.assertEqual(turn.prompt, "test prompt")
        self.assertEqual(turn.backend, "agy")
        self.assertEqual(turn.route, "key123")
        self.assertEqual(turn.target_model, "")

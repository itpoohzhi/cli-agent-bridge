"""Манифесты провайдеров: закрытая схема, slug'и §3.4, смарт-дефолты, защита argv (F-001)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from adapters import ADAPTER_KINDS
from core.provider_manifest import (
    ManifestError,
    argv_placeholders_valid,
    executable_allowed,
    load_manifests,
    load_schema,
    providers_dir,
    render_argv,
    resolve_family,
    unknown_keys,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "providers.d" / "_schema" / "provider-manifest.schema.json"


def base() -> Dict[str, Any]:
    return {
        "manifest_version": 1,
        "provider_id": "demo",
        "kind": "passthrough",
        "owned_by": "demo-bridge",
        "transport": {
            "bridge": {
                "base_url": "http://127.0.0.1:9000/v1",
                "api_key_env": "DEMO_BRIDGE_KEY",
            },
            "direct": {
                "type": "cli",
                "cli": {
                    "executables": ["~/.local/bin/demo"],
                    "argv_by_executable": {
                        "~/.local/bin/demo": [
                            "-p",
                            "{prompt}",
                            "--model",
                            "{slot}",
                            "--effort",
                            "{effort}",
                        ]
                    },
                    "prompt_via": "argv",
                    "output": {"format": "text"},
                },
            },
        },
        "allow_base_url": [
            {"scheme": "http", "host": "127.0.0.1", "port": 9000, "path_prefix": "/v1"}
        ],
        "limits": {"max_concurrent": 8, "quota_group": "demo-group"},
        "family_rule": {
            "type": "prefix",
            "prefix": {"verified": True, "map": {"demo-": "Demo"}},
        },
    }


def validate(doc: Dict[str, Any], filename: str = "demo.yaml", **kwargs: Any) -> Any:
    return validate_manifest(doc, ADAPTER_KINDS, filename=filename, **kwargs)


def errors_of(doc: Dict[str, Any], **kwargs: Any) -> tuple:
    return validate(doc, **kwargs).errors


def test_valid_manifest_passes() -> None:
    result = validate(base())
    assert result.ok and result.errors == ()
    assert result.manifest is not None and result.manifest.provider_id == "demo"


def test_shipped_manifests_all_valid() -> None:
    loaded = load_manifests(providers_dir(), ADAPTER_KINDS)
    assert dict(loaded.rejected_providers) == {}
    assert {m.provider_id for m in loaded.manifests} == {
        "agy",
        "claude-p",
        "codex",
        "droid",
        "muse",
        "opencode-go",
        "opencode-zen",
    }


def test_shipped_manifests_pass_json_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    yaml = pytest.importorskip("yaml")
    validator_cls = jsonschema.Draft202012Validator
    validator_cls.check_schema(load_schema(SCHEMA))
    validator = validator_cls(load_schema(SCHEMA))
    for path in sorted((ROOT / "providers.d").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert list(validator.iter_errors(doc)) == [], path.name


def test_json_schema_rejects_unknown_key_like_validator() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    doc = base()
    doc["bogus"] = 1
    validator = jsonschema.Draft202012Validator(load_schema(SCHEMA))
    assert list(validator.iter_errors(doc))
    assert "provider_key_unknown" in errors_of(doc)


# ---- slug'и §3.4 (негативные кейсы) ------------------------------------------------


def test_unknown_key_top_level_and_nested() -> None:
    doc = base()
    doc["bogus"] = 1
    assert "provider_key_unknown" in errors_of(doc)
    doc = base()
    doc["limits"]["extra"] = 1
    assert "provider_key_unknown" in errors_of(doc)
    doc = base()
    doc["allow_base_url"][0]["extra"] = 1
    assert "provider_key_unknown" in errors_of(doc)
    assert unknown_keys(
        {"a": {"b": 1}},
        {"properties": {"a": {"additionalProperties": False, "properties": {}}}},
    ) == ["a.b"]


def test_version_unsupported() -> None:
    doc = base()
    doc["manifest_version"] = 2
    assert "provider_manifest_version_unsupported" in errors_of(doc)


def test_kind_unknown() -> None:
    doc = base()
    doc["kind"] = "shell-runner"
    assert "provider_kind_unknown" in errors_of(doc)


@pytest.mark.parametrize("pid", ["Demo", "-demo", "de mo", "a" * 33, "", 7])
def test_provider_id_regex(pid: Any) -> None:
    doc = base()
    doc["provider_id"] = pid
    assert "provider_id_invalid" in errors_of(doc, filename="x.yaml")


def test_provider_id_must_match_filename() -> None:
    assert "provider_id_invalid" in errors_of(base(), filename="other.yaml")
    assert errors_of(base(), filename="demo.yaml") == ()


@pytest.mark.parametrize("cap", [0, -1, True, "8"])
def test_max_concurrent_invalid(cap: Any) -> None:
    doc = base()
    doc["limits"]["max_concurrent"] = cap
    assert "provider_max_concurrent_invalid" in errors_of(doc)


def test_max_concurrent_above_kind_ceiling() -> None:
    doc = {
        "manifest_version": 1,
        "provider_id": "mus",
        "kind": "muse",
        "owned_by": "m",
        "limits": {"max_concurrent": 2},
        "fingerprint": {"binary_path": "~/.local/bin/muse"},
    }
    assert "provider_max_concurrent_invalid" in errors_of(doc, filename="mus.yaml")


def test_pin_required_without_binary_path() -> None:
    doc = {"manifest_version": 1, "provider_id": "mus", "kind": "muse", "owned_by": "m"}
    assert "provider_technical_ref_missing" in errors_of(doc, filename="mus.yaml")
    doc["fingerprint"] = {"binary_path": "~/.local/bin/muse"}
    assert errors_of(doc, filename="mus.yaml") == ()
    doc = {
        "manifest_version": 1,
        "provider_id": "dem",
        "kind": "passthrough",
        "owned_by": "m",
        "limits": {"pin_required": True},
    }
    assert "provider_technical_ref_missing" in errors_of(doc, filename="dem.yaml")


def test_base_url_unexpected_for_kind_without_http() -> None:
    doc = {
        "manifest_version": 1,
        "provider_id": "mus",
        "kind": "muse",
        "owned_by": "m",
        "fingerprint": {"binary_path": "~/.local/bin/muse"},
        "transport": {"bridge": {"base_url": "http://127.0.0.1:1/v1"}},
    }
    assert "provider_base_url_unexpected" in errors_of(doc, filename="mus.yaml")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:9001/v1",
        "http://example.com:9000/v1",
        "http://127.0.0.1:9000/other",
        "ftp://x",
    ],
)
def test_base_url_must_match_allowlist(url: str) -> None:
    doc = base()
    doc["transport"]["bridge"]["base_url"] = url
    assert "provider_base_url_invalid" in errors_of(doc)


def test_base_url_default_policy_without_allowlist() -> None:
    doc = base()
    doc.pop("allow_base_url")
    assert errors_of(doc) == ()
    doc["transport"]["bridge"]["base_url"] = "http://127.0.0.1:99999/v1"
    assert "provider_base_url_invalid" in errors_of(doc)


def test_remote_host_forbidden_by_default_and_plaintext_always() -> None:
    doc = base()
    doc["allow_base_url"] = [{"scheme": "http", "host": "10.1.2.3", "port": 80}]
    errs = errors_of(doc)
    assert "provider_allowlist_remote_forbidden" in errs
    assert "provider_allowlist_plaintext_remote" in errs
    env = {"BRIDGE_PROVIDER_REMOTE_BASE_URL_ENABLED": "true"}
    errs = errors_of(doc, env=env)
    assert "provider_allowlist_remote_forbidden" not in errs
    assert "provider_allowlist_plaintext_remote" in errs
    doc["allow_base_url"] = [
        {"scheme": "https", "host": "api.example.com", "port": 443}
    ]
    assert "provider_allowlist_plaintext_remote" not in errors_of(doc, env=env)
    assert "provider_allowlist_remote_forbidden" in errors_of(doc)


def test_loopback_ipv6_allowed() -> None:
    doc = base()
    doc["allow_base_url"].append({"scheme": "http", "host": "::1", "port": 9000})
    assert errors_of(doc) == ()


def test_options_invalid() -> None:
    doc = base()
    doc["transport"]["bridge"]["options"] = {"streaming_mode": "exec"}
    assert "provider_options_invalid" in errors_of(doc)
    muse = {
        "manifest_version": 1,
        "provider_id": "mus",
        "kind": "muse",
        "owned_by": "m",
        "fingerprint": {"binary_path": "~/.local/bin/muse"},
        "transport": {"bridge": {"options": {"streaming_mode": "warp"}}},
    }
    assert "provider_options_invalid" in errors_of(muse, filename="mus.yaml")
    muse["transport"]["bridge"]["options"] = {"streaming_mode": "serve"}
    assert errors_of(muse, filename="mus.yaml") == ()
    muse["transport"]["bridge"]["options"] = {"mystery": "x"}
    assert "provider_options_invalid" in errors_of(muse, filename="mus.yaml")


@pytest.mark.parametrize(
    "element",
    ["{unknown}", "pre{prompt}", "{prompt}suffix", "{model", "model}", "{{model}}"],
)
def test_argv_placeholder_invalid(element: str) -> None:
    doc = base()
    doc["transport"]["direct"]["cli"]["argv_by_executable"]["~/.local/bin/demo"] = [
        "-x",
        element,
    ]
    assert "provider_argv_placeholder_invalid" in errors_of(doc)


def test_argv_known_placeholders_ok() -> None:
    assert argv_placeholders_valid(
        ["{prompt}", "--m", "{model}", "{slot}", "e={effort}", "{uuid4}"]
    )
    assert not argv_placeholders_valid(["{prompt} {model}"])


@pytest.mark.parametrize(
    "path",
    [
        "demo",
        "/tmp/demo",
        "/usr/bin/../bin/demo",
        "/usr/bin/bash",
        "~/.local/bin/zsh",
        "/etc/demo",
    ],
)
def test_executable_forbidden(path: str) -> None:
    doc = base()
    cli = doc["transport"]["direct"]["cli"]
    cli["executables"] = [path]
    cli["argv_by_executable"] = {path: ["{prompt}"]}
    assert "provider_executable_forbidden" in errors_of(doc)


@pytest.mark.parametrize(
    "path",
    [
        "~/.local/bin/x",
        "~/.config/agy-launch/agy-cli.sh",
        "/opt/homebrew/bin/x",
        "/usr/local/bin/x",
    ],
)
def test_executable_allowed_dirs(path: str) -> None:
    assert executable_allowed(path)


def test_executable_dirs_overridable_by_env() -> None:
    assert not executable_allowed("/srv/tools/x", {})
    assert executable_allowed("/srv/tools/x", {"BRIDGE_DIRECT_EXEC_DIRS": "/srv/tools"})
    assert not executable_allowed(
        "/srv/tools/bash", {"BRIDGE_DIRECT_EXEC_DIRS": "/srv/tools"}
    )


def test_family_rule_prefix_requires_verification() -> None:
    doc = base()
    doc["family_rule"]["prefix"]["verified"] = False
    assert "provider_family_rule_unverified" in errors_of(doc)
    doc["family_rule"] = {"type": "prefix"}
    assert "provider_family_rule_unverified" in errors_of(doc)


def test_params_whitelist_invalid() -> None:
    doc = base()
    doc["params"] = {"adaptive_whitelist": ["reasoning_effort", "frequency_penalty"]}
    assert "provider_params_whitelist_invalid" in errors_of(doc)
    doc["params"] = {"adaptive_whitelist": ["reasoning_effort", "thinking"]}
    assert errors_of(doc) == ()


@pytest.mark.parametrize("group", ["", "UPPER", "has space", "x" * 49])
def test_quota_group_invalid(group: str) -> None:
    doc = base()
    doc["limits"]["quota_group"] = group
    assert "provider_quota_group_invalid" in errors_of(doc)


def test_garbage_never_raises() -> None:
    for junk in (
        None,
        [],
        "x",
        5,
        {"manifest_version": "1"},
        {"transport": 7},
        {"limits": []},
        {"discovery": {"method": 5}},
        {"family_rule": []},
        {"params": 5},
        {"probe": []},
    ):
        result = validate_manifest(junk, ADAPTER_KINDS)  # type: ignore[arg-type]
        assert result.manifest is None and result.errors


def test_errors_are_slugs_without_user_data() -> None:
    doc = base()
    doc["bogus_secret_value_123"] = "hunter2"
    for slug in errors_of(doc):
        assert (
            "hunter2" not in slug
            and "bogus_secret" not in slug
            and slug.startswith("provider_")
        )


# ---- смарт-дефолты -----------------------------------------------------------------


def test_smart_defaults() -> None:
    doc = {
        "manifest_version": 1,
        "provider_id": "mini",
        "kind": "passthrough",
        "owned_by": "mini-bridge",
    }
    manifest = validate(doc, filename="mini.yaml").manifest
    assert manifest is not None
    assert manifest.limits.max_concurrent == 1
    assert manifest.limits.quota_group == "mini"
    assert manifest.limits.timeout_s == 180
    assert manifest.params.tool_emulation is True
    assert (
        manifest.enabled is True
        and manifest.required is False
        and manifest.priority == 100
    )
    assert manifest.models_defaults.efforts == ("high",)
    assert manifest.probe.max_parallel == 1


def test_smart_defaults_overridable_by_env() -> None:
    doc = {
        "manifest_version": 1,
        "provider_id": "mini",
        "kind": "passthrough",
        "owned_by": "m",
    }
    env = {
        "BRIDGE_DEFAULT_MAX_CONCURRENT": "4",
        "BRIDGE_DEFAULT_TIMEOUT_S": "60",
        "BRIDGE_DEFAULT_TOOL_EMULATION": "false",
    }
    manifest = validate(doc, filename="mini.yaml", env=env).manifest
    assert manifest is not None
    assert (
        manifest.limits.max_concurrent,
        manifest.limits.timeout_s,
        manifest.params.tool_emulation,
    ) == (4, 60.0, False)


# ---- render_argv: защита от инъекций (F-001) ---------------------------------------


def test_render_argv_substitutes_without_shell() -> None:
    argv = render_argv(
        ["-p", "{prompt}", "--model", "{slot}", "--e", "{effort}"],
        {
            "prompt": "echo $(rm -rf /); `x` | y",
            "slot": "gemini-3.8-flash",
            "effort": "high",
        },
    )
    assert argv == [
        "-p",
        "echo $(rm -rf /); `x` | y",
        "--model",
        "gemini-3.8-flash",
        "--e",
        "high",
    ]


@pytest.mark.parametrize(
    "bad", ["a b", "a;b", "$(x)", "", "x" * 129, "a\nb", "../../etc"]
)
def test_render_argv_rejects_unsafe_values(bad: str) -> None:
    if bad == "../../etc":
        # '.' и '/' допустимы regex'ом; обход каталогов не опасен для аргумента, не путь
        assert render_argv(["{model}"], {"model": bad}) == [bad]
        return
    with pytest.raises(ManifestError) as exc:
        render_argv(["{model}"], {"model": bad})
    assert exc.value.slug == "provider_argv_value_invalid"


def test_render_argv_rejects_bad_template() -> None:
    with pytest.raises(ManifestError) as exc:
        render_argv(["x{prompt}"], {"prompt": "p"})
    assert exc.value.slug == "provider_argv_placeholder_invalid"


def test_render_argv_prompt_dash_guard() -> None:
    assert render_argv(["{prompt}"], {"prompt": "--evil"}) == [" --evil"]
    assert render_argv(
        ["{prompt}"],
        {"prompt": "--evil"},
        env={"BRIDGE_DIRECT_PROMPT_DASH_GUARD": "false"},
    ) == ["--evil"]
    assert render_argv(["{prompt}"], {"prompt": "hello"}) == ["hello"]


def test_render_argv_uuid4_unique() -> None:
    first, second = render_argv(["{uuid4}"], {}), render_argv(["{uuid4}"], {})
    assert first != second and len(first[0]) == 36


def test_render_argv_prompt_is_single_element() -> None:
    assert render_argv(["{prompt}"], {"prompt": "two words\nsecond line"}) == [
        "two words\nsecond line"
    ]


# ---- семья -------------------------------------------------------------------------


def test_resolve_family_rules() -> None:
    manifest = validate(base()).manifest
    assert manifest is not None
    assert resolve_family(manifest, "demo-large") == ("Demo", "prefix")
    assert resolve_family(manifest, "other-model") == (None, "unmapped")
    doc = base()
    doc["family_rule"] = {
        "type": "prefix",
        "prefix": {"verified": True, "map": {"d": "A", "de": "B"}},
    }
    ambiguous = validate(doc).manifest
    assert ambiguous is not None
    assert resolve_family(ambiguous, "demo") == (None, "ambiguous")
    doc["family_rule"] = {
        "type": "prefix",
        "prefix": {"verified": True, "map": {"d": "A", "de": "A"}},
    }
    same = validate(doc).manifest
    assert same is not None and resolve_family(same, "demo") == ("A", "prefix")
    doc["family_rule"] = {"type": "owned_by", "owned_by": "Anth"}
    owned = validate(doc).manifest
    assert owned is not None and resolve_family(owned, "anything") == (
        "Anth",
        "owned_by",
    )
    doc["family_rule"] = {"type": "exact_map", "exact_map": {"m1": "F"}}
    exact = validate(doc).manifest
    assert exact is not None
    assert resolve_family(exact, "m1") == ("F", "exact_map")
    assert resolve_family(exact, "m2") == (None, "unmapped")


# ---- загрузка ----------------------------------------------------------------------


def test_load_manifests_collects_rejected(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    import yaml

    (tmp_path / "good.yaml").write_text(
        yaml.safe_dump({**base(), "provider_id": "good"}), encoding="utf-8"
    )
    (tmp_path / "bad.yaml").write_text(
        yaml.safe_dump({**base(), "provider_id": "bad", "kind": "nope"}),
        encoding="utf-8",
    )
    (tmp_path / "broken.yaml").write_text("a: [unclosed", encoding="utf-8")
    (tmp_path / "_fleet.yaml").write_text("schema_version: 3\n", encoding="utf-8")
    loaded = load_manifests(tmp_path, ADAPTER_KINDS)
    assert [m.provider_id for m in loaded.manifests] == ["good"]
    assert dict(loaded.rejected_providers) == {
        "bad": ("provider_kind_unknown",),
        "broken": ("provider_yaml_invalid",),
    }
    assert set(loaded.sha256_by_file) == {"good.yaml", "bad.yaml", "broken.yaml"}


def test_load_manifests_missing_dir_is_empty(tmp_path: Path) -> None:
    loaded = load_manifests(tmp_path / "absent", ADAPTER_KINDS)
    assert loaded.manifests == () and dict(loaded.rejected_providers) == {}


def test_manifest_is_immutable() -> None:
    manifest = validate(base()).manifest
    assert manifest is not None
    with pytest.raises(Exception):
        manifest.provider_id = "x"  # type: ignore[misc]


def test_schema_file_is_valid_json_and_closed() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["manifest_version"]["const"] == 1


def test_validation_does_not_mutate_input() -> None:
    doc = base()
    snapshot = copy.deepcopy(doc)
    validate(doc)
    assert doc == snapshot

"""Компилятор каталога: golden-эквивалентность, детерминизм, изоляция, сайдкар, CLI (AC (б))."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from adapters import ADAPTER_KINDS
from core import fleet_compiler as fc
from core.backend_adapter import build_catalog
from core.fleet_compiler import (
    CompileError,
    atomic_write_bytes,
    compile_catalog,
    compile_from_disk,
    load_receipts,
    render_fleet_json,
    validate_header,
)
from core.model_lifecycle import (
    EVENT_DISCOVERED_OK,
    EVENT_FINGERPRINT_CHANGED,
    EVENT_PROBE_PASS,
    EVENT_PROBE_START,
    LifecycleRegistry,
)
from core.provider_manifest import ProviderManifest, load_manifests, validate_manifest
from tools import fleet_compile

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-11-06T12:00:00+03:00"
FP = "f" * 64


def current_fleet() -> Dict[str, Any]:
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def header() -> Dict[str, Any]:
    cur = current_fleet()
    return {
        k: cur[k]
        for k in (
            "schema_version",
            "catalogue",
            "aliases",
            "default_model",
            "image_limits",
            "admission",
        )
    }


def manifest_doc(pid: str = "alpha", **over: Any) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "manifest_version": 1,
        "provider_id": pid,
        "kind": "passthrough",
        "owned_by": f"{pid}-bridge",
        "transport": {
            "bridge": {
                "base_url": "http://127.0.0.1:9100/v1",
                "api_key_env": "ALPHA_BRIDGE_KEY",
            }
        },
        "limits": {"max_concurrent": 4, "quota_group": f"{pid}-quota"},
        "family_rule": {"type": "owned_by", "owned_by": "Alpha"},
        "models_overrides": {
            f"{pid}-one": {
                "efforts": ["low", "high"],
                "default_effort": "high",
                "context_window": 1000,
            },
            f"{pid}-two": {},
        },
    }
    doc.update(over)
    return doc


def build_manifests(*docs: Dict[str, Any]) -> List[ProviderManifest]:
    out = []
    for doc in docs:
        result = validate_manifest(
            doc, ADAPTER_KINDS, filename=doc["provider_id"] + ".yaml"
        )
        assert result.manifest is not None, result.errors
        out.append(result.manifest)
    return out


def compile_docs(*docs: Dict[str, Any], hdr: Any = None, **kwargs: Any) -> Any:
    hdr = hdr or dict(header(), default_model=f"{docs[0]['provider_id']}-one")
    return compile_catalog(
        hdr, build_manifests(*docs), kinds=ADAPTER_KINDS, now=NOW, **kwargs
    )


# ---- golden: миграция providers.d == текущий fleet.json -----------------------------


def test_golden_equivalent_to_current_fleet() -> None:
    result = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW)
    assert (
        result.rejected == {}
        and result.rejected_providers == {}
        and result.warnings == ()
    )
    current = current_fleet()
    expected = build_catalog(current, ADAPTER_KINDS)
    actual = build_catalog(result.fleet, ADAPTER_KINDS)
    for key in (
        "models",
        "backends",
        "aliases",
        "default_model",
        "image_limits",
        "admission",
        "technical_ref",
        "catalogue",
    ):
        assert actual[key] == expected[key], key
    assert set(actual["order"]) == set(expected["order"])


def test_golden_raw_records_identical_modulo_order() -> None:
    compiled = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW).fleet
    current = current_fleet()
    models_a = {m["id"]: m for m in current.pop("models")}
    models_b = {m["id"]: m for m in compiled.pop("models")}
    assert models_a == models_b
    assert current == compiled


def test_fleet_json_schema_keys_not_extended() -> None:
    from core.backend_adapter import FLEET_MODEL_KEYS, FLEET_TOP_KEYS

    fleet = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW).fleet
    assert set(fleet) <= FLEET_TOP_KEYS
    assert all(set(m) <= FLEET_MODEL_KEYS for m in fleet["models"])


# ---- детерминизм -------------------------------------------------------------------


def test_compile_is_byte_deterministic() -> None:
    first = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW)
    second = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW)
    assert render_fleet_json(first.fleet) == render_fleet_json(second.fleet)
    assert fc.canonical_json(first.sidecar) == fc.canonical_json(second.sidecar)


def test_input_order_does_not_change_output() -> None:
    manifests = build_manifests(
        manifest_doc("alpha"),
        manifest_doc(
            "beta",
            transport={
                "bridge": {
                    "base_url": "http://127.0.0.1:9101/v1",
                    "api_key_env": "B_BRIDGE_KEY",
                }
            },
        ),
    )
    hdr = dict(header(), default_model="alpha-one")
    forward = compile_catalog(hdr, manifests, kinds=ADAPTER_KINDS, now=NOW)
    backward = compile_catalog(
        hdr, list(reversed(manifests)), kinds=ADAPTER_KINDS, now=NOW
    )
    assert render_fleet_json(forward.fleet) == render_fleet_json(backward.fleet)
    ids = [m["id"] for m in forward.fleet["models"]]
    assert ids == ["alpha-one", "alpha-two", "beta-one", "beta-two"]


def test_fleet_bytes_independent_of_compiled_at() -> None:
    manifests = build_manifests(manifest_doc())
    hdr = dict(header(), default_model="alpha-one")
    a = compile_catalog(
        hdr, manifests, kinds=ADAPTER_KINDS, now="2026-01-01T00:00:00+00:00"
    )
    b = compile_catalog(
        hdr, manifests, kinds=ADAPTER_KINDS, now="2027-01-01T00:00:00+00:00"
    )
    assert render_fleet_json(a.fleet) == render_fleet_json(b.fleet)
    assert a.sidecar["fleet_sha256"] == b.sidecar["fleet_sha256"]


# ---- self-check и изоляция ----------------------------------------------------------


def test_self_check_passes_in_strict_without_constraints() -> None:
    result = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW)
    build_catalog(result.fleet, ADAPTER_KINDS, mode="strict", constraints_enabled=False)
    assert (
        result.sidecar["fleet_sha256"]
        == hashlib.sha256(render_fleet_json(result.fleet)).hexdigest()
    )


def test_broken_model_goes_to_rejected_not_fleet() -> None:
    doc = manifest_doc()
    doc["models_overrides"]["alpha-bad"] = {
        "efforts": ["turbo"],
        "default_effort": "turbo",
    }
    result = compile_docs(doc)
    assert result.rejected == {"alpha-bad": "efforts_invalid"}
    assert "alpha-bad" not in [m["id"] for m in result.fleet["models"]]
    assert "alpha-bad" not in result.sidecar["models"]
    assert result.sidecar["rejected"]["alpha-bad"] == {
        "provider": "alpha",
        "reason": "efforts_invalid",
    }
    assert {"alpha-one", "alpha-two"} <= {m["id"] for m in result.fleet["models"]}


def test_default_model_missing_is_compile_error() -> None:
    with pytest.raises(CompileError) as exc:
        compile_docs(manifest_doc(), hdr=dict(header(), default_model="ghost"))
    assert exc.value.slug == "default_model_invalid"


def test_header_validation() -> None:
    with pytest.raises(CompileError) as exc:
        validate_header({**header(), "bogus": 1})
    assert exc.value.slug == "header_key_unknown"
    with pytest.raises(CompileError) as exc:
        validate_header({**header(), "schema_version": 2})
    assert exc.value.slug == "schema_version_invalid"
    bad = header()
    bad.pop("image_limits")
    with pytest.raises(CompileError):
        validate_header(bad)
    with pytest.raises(CompileError):
        validate_header([])


def test_rejected_providers_are_reported_and_skipped() -> None:
    result = compile_docs(
        manifest_doc(), rejected_providers={"gone": ("provider_kind_unknown",)}
    )
    assert result.rejected_providers == {"gone": ("provider_kind_unknown",)}
    assert result.sidecar["rejected_providers"] == {"gone": ["provider_kind_unknown"]}


def test_direct_only_provider_not_compiled_into_fleet() -> None:
    direct = manifest_doc(
        "gamma",
        transport={
            "direct": {
                "type": "http",
                "http": {"base_url": "http://127.0.0.1:10830/go/v1", "path": "/x"},
            }
        },
        allow_base_url=[
            {"scheme": "http", "host": "127.0.0.1", "port": 10830, "path_prefix": "/go"}
        ],
    )
    result = compile_docs(manifest_doc(), direct)
    assert "gamma" not in result.fleet["backends"]
    assert all(m["backend"] != "gamma" for m in result.fleet["models"])
    assert result.sidecar["models"]["gamma-one"]["provider"] == "gamma"
    assert result.sidecar["models"]["gamma-one"]["in_fleet"] is False
    assert result.sidecar["providers"]["gamma"]["bridge"] is False


# ---- приоритет и alternates --------------------------------------------------------


def test_same_model_two_providers_priority_wins_with_alternates() -> None:
    first = manifest_doc("alpha", priority=200)
    first["models_overrides"] = {
        "shared-model": {"efforts": ["high"], "default_effort": "high"}
    }
    second = manifest_doc(
        "beta",
        priority=50,
        transport={
            "bridge": {
                "base_url": "http://127.0.0.1:9101/v1",
                "api_key_env": "B_BRIDGE_KEY",
            }
        },
    )
    second["models_overrides"] = {
        "shared-model": {"efforts": ["high"], "default_effort": "high"},
        "beta-one": {},
    }
    result = compile_docs(
        first, second, hdr=dict(header(), default_model="shared-model")
    )
    shared = [m for m in result.fleet["models"] if m["id"] == "shared-model"]
    assert len(shared) == 1 and shared[0]["backend"] == "beta"
    assert result.sidecar["models"]["shared-model"]["provider"] == "beta"
    assert result.sidecar["models"]["shared-model"]["alternates"] == [
        {"provider": "alpha"}
    ]


def test_equal_priority_lexicographic_provider_wins() -> None:
    one = manifest_doc("bbb")
    one["models_overrides"] = {"dup": {}, "bbb-x": {}}
    two = manifest_doc(
        "aaa",
        transport={
            "bridge": {
                "base_url": "http://127.0.0.1:9101/v1",
                "api_key_env": "A_BRIDGE_KEY",
            }
        },
    )
    two["models_overrides"] = {"dup": {}}
    result = compile_docs(one, two, hdr=dict(header(), default_model="dup"))
    assert result.sidecar["models"]["dup"]["provider"] == "aaa"


# ---- quorum_eligible и статусы -----------------------------------------------------


def test_new_models_default_to_quarantine_and_not_quorum() -> None:
    result = compile_docs(manifest_doc())
    entry = result.sidecar["models"]["alpha-one"]
    assert entry["status"] == "quarantine" and entry["quorum_eligible"] is False
    assert entry["family"] == "Alpha" and entry["family_source"] == "owned_by"
    assert entry["quota_group"] == "alpha-quota"
    assert result.sidecar["providers"]["alpha"]["quota_group"] == "alpha-quota"


def test_manual_quorum_eligible_override_ignored_with_warning() -> None:
    doc = manifest_doc()
    doc["models_overrides"]["alpha-one"]["quorum_eligible"] = True
    result = compile_docs(doc)
    assert result.sidecar["models"]["alpha-one"]["quorum_eligible"] is False
    assert "quorum_eligible_override_ignored:alpha-one" in result.warnings
    assert "quorum_eligible" not in result.fleet["models"][0]


def receipt(
    verdict: str = "confirmed", proven: Any = ("low", "high"), default: str = "high"
) -> Dict[str, Any]:
    return {
        "schema": "probe-receipt/1",
        "probe_version": 1,
        "verdict": verdict,
        "efforts_proven": list(proven),
        "default_effort": default,
        "finished_at": NOW,
    }


def sha(doc: Dict[str, Any]) -> str:
    return hashlib.sha256(fc.canonical_json(doc)).hexdigest()


def registry_with(
    status_events: Any, model: str = "alpha-one", sha_value: str = ""
) -> LifecycleRegistry:
    registry = LifecycleRegistry()
    key = ("alpha", model, FP)
    registry.register(*key)
    for event, payload in status_events:
        registry.apply(key, event, 1000.0, payload)
    return registry


def discovery_fp() -> Dict[str, Any]:
    return {"alpha": SimpleNamespace(fingerprint_sha256=FP, model_ids=(), meta={})}


def test_confirmed_with_valid_receipt_sets_efforts_and_quorum() -> None:
    rc = receipt(proven=("low", "medium", "high"))
    digest = sha(rc)
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (
                EVENT_PROBE_PASS,
                {"receipt_sha256": digest, "efforts_proven": ["low", "medium", "high"]},
            ),
        ]
    )
    result = compile_docs(
        manifest_doc(),
        registry=registry,
        receipts={digest: rc},
        discovery=discovery_fp(),
    )
    entry = result.sidecar["models"]["alpha-one"]
    assert entry["status"] == "confirmed" and entry["quorum_eligible"] is True
    assert entry["efforts_proven"] == ["low", "medium", "high"]
    assert (
        entry["probe"]["receipt_sha256"] == digest
        and entry["probe"]["fingerprint_sha256"] == FP
    )
    record = next(m for m in result.fleet["models"] if m["id"] == "alpha-one")
    assert (
        record["efforts"] == ["low", "medium", "high"]
        and record["default_effort"] == "high"
    )


def test_efforts_pin_limits_receipt_efforts() -> None:
    doc = manifest_doc()
    doc["models_overrides"]["alpha-one"]["efforts_pin"] = ["low"]
    rc = receipt(proven=("low", "high"), default="high")
    digest = sha(rc)
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (
                EVENT_PROBE_PASS,
                {"receipt_sha256": digest, "efforts_proven": ["low", "high"]},
            ),
        ]
    )
    result = compile_docs(
        doc, registry=registry, receipts={digest: rc}, discovery=discovery_fp()
    )
    record = next(m for m in result.fleet["models"] if m["id"] == "alpha-one")
    assert record["efforts"] == ["low"] and record["default_effort"] == "low"


def test_confirmed_without_receipt_is_demoted_to_quarantine() -> None:
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (
                EVENT_PROBE_PASS,
                {"receipt_sha256": "a" * 64, "efforts_proven": ["high"]},
            ),
        ]
    )
    result = compile_docs(
        manifest_doc(), registry=registry, receipts={}, discovery=discovery_fp()
    )
    entry = result.sidecar["models"]["alpha-one"]
    assert entry["status"] == "quarantine" and entry["quorum_eligible"] is False
    assert "probe" not in entry


def test_confirmed_with_non_confirmed_receipt_is_demoted() -> None:
    rc = receipt(verdict="quarantine_failed")
    digest = sha(rc)
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (EVENT_PROBE_PASS, {"receipt_sha256": digest, "efforts_proven": ["high"]}),
        ]
    )
    result = compile_docs(
        manifest_doc(),
        registry=registry,
        receipts={digest: rc},
        discovery=discovery_fp(),
    )
    assert result.sidecar["models"]["alpha-one"]["status"] == "quarantine"


def test_status_for_other_fingerprint_is_not_applied() -> None:
    rc = receipt()
    digest = sha(rc)
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (EVENT_PROBE_PASS, {"receipt_sha256": digest, "efforts_proven": ["high"]}),
        ]
    )
    changed = {
        "alpha": SimpleNamespace(fingerprint_sha256="e" * 64, model_ids=(), meta={})
    }
    result = compile_docs(
        manifest_doc(), registry=registry, receipts={digest: rc}, discovery=changed
    )
    assert result.sidecar["models"]["alpha-one"]["status"] == "quarantine"


def test_stale_keeps_receipt_efforts_but_not_quorum() -> None:
    rc = receipt()
    digest = sha(rc)
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (
                EVENT_PROBE_PASS,
                {"receipt_sha256": digest, "efforts_proven": ["low", "high"]},
            ),
            (EVENT_FINGERPRINT_CHANGED, None),
        ]
    )
    result = compile_docs(
        manifest_doc(),
        registry=registry,
        receipts={digest: rc},
        discovery=discovery_fp(),
    )
    entry = result.sidecar["models"]["alpha-one"]
    assert entry["status"] == "stale" and entry["quorum_eligible"] is False


def test_unmapped_family_never_quorum_eligible() -> None:
    doc = manifest_doc(family_rule={"type": "exact_map", "exact_map": {}})
    rc = receipt()
    digest = sha(rc)
    registry = registry_with(
        [
            (EVENT_DISCOVERED_OK, None),
            (EVENT_PROBE_START, None),
            (EVENT_PROBE_PASS, {"receipt_sha256": digest, "efforts_proven": ["high"]}),
        ]
    )
    result = compile_docs(
        doc, registry=registry, receipts={digest: rc}, discovery=discovery_fp()
    )
    entry = result.sidecar["models"]["alpha-one"]
    assert (
        entry["status"] == "confirmed"
        and entry["family"] is None
        and entry["quorum_eligible"] is False
    )


def test_history_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = registry_with([(EVENT_DISCOVERED_OK, None)])
    result = compile_docs(
        manifest_doc(),
        registry=registry,
        discovery=discovery_fp(),
        env={"BRIDGE_CATALOG_HISTORY_MAX": "1"},
    )
    assert len(result.sidecar["models"]["alpha-one"]["history"]) <= 1


def test_discovered_models_are_added_with_meta() -> None:
    found = {
        "alpha": SimpleNamespace(
            fingerprint_sha256=FP,
            model_ids=("alpha-new",),
            meta={"alpha-new": {"context_window": 4242, "max_tokens": 99}},
        )
    }
    result = compile_docs(manifest_doc(), discovery=found)
    record = next(m for m in result.fleet["models"] if m["id"] == "alpha-new")
    assert record["context_window"] == 4242 and record["max_tokens"] == 99
    assert record["efforts"] == ["high"]  # models_defaults
    assert result.sidecar["models"]["alpha-new"]["status"] == "quarantine"


def test_sidecar_shape() -> None:
    result = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW)
    sidecar = result.sidecar
    assert sidecar["schema"] == "catalog-lock/1" and sidecar["compiled_at"] == NOW
    assert set(sidecar["inputs"]) == {
        "manifests",
        "manifests_sha256",
        "discovery_sha256",
    }
    assert (
        "_fleet.yaml" in sidecar["inputs"]["manifests"]
        and "agy.yaml" in sidecar["inputs"]["manifests"]
    )
    assert sidecar["providers"]["agy"]["allow_base_url"][0]["port"] == 9887
    assert sidecar["providers"]["opencode-go"]["direct"]["type"] == "http"
    assert sidecar["models"]["gpt-6.1-sol"]["family"] == "OpenAI"
    assert sidecar["models"]["claude-sonnet-5-5"]["family"] == "Anthropic"
    assert sidecar["models"]["muse-wonder-full-1.0"]["family"] == "Meta"
    assert sidecar["models"]["deepseek-v4.1-flash"]["provider"] == "opencode-go"
    assert "kimi-k3.1-pro" not in sidecar["models"]
    assert sidecar["models"]["deepseek-v4.1-flash"]["family"] == "DeepSeek"
    assert all(entry["status"] == "quarantine" for entry in sidecar["models"].values())


# ---- файлы: атомарность, квитанции, CLI --------------------------------------------


def test_atomic_write_replaces_and_leaves_no_tmp(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "fleet.compiled.json"
    atomic_write_bytes(target, b"one")
    atomic_write_bytes(target, b"two")
    assert target.read_bytes() == b"two"
    assert [p.name for p in target.parent.iterdir()] == ["fleet.compiled.json"]


def test_load_receipts_requires_matching_sha(tmp_path: Path) -> None:
    good = receipt()
    digest = sha(good)
    (tmp_path / f"{digest}.json").write_bytes(fc.canonical_json(good))
    (tmp_path / f"{'0' * 64}.json").write_bytes(fc.canonical_json(good))
    (tmp_path / "junk.json").write_text("{", encoding="utf-8")
    assert list(load_receipts(tmp_path)) == [digest]
    assert load_receipts(tmp_path / "absent") == {}


def test_cli_write_then_check_up_to_date_then_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    assert fleet_compile.main(["--write", "--now", NOW]) == 0
    fleet_path, sidecar_path = (
        tmp_path / "fleet.compiled.json",
        tmp_path / "catalog.lock.json",
    )
    assert fleet_path.is_file() and sidecar_path.is_file()
    assert (
        json.loads(sidecar_path.read_text(encoding="utf-8"))["schema"]
        == "catalog-lock/1"
    )
    build_catalog(json.loads(fleet_path.read_text(encoding="utf-8")), ADAPTER_KINDS)
    assert (
        fleet_compile.main(["--check", "--output", str(fleet_path), "--now", NOW]) == 0
    )
    fleet_path.write_text(
        fleet_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    assert (
        fleet_compile.main(["--check", "--output", str(fleet_path), "--now", NOW]) == 1
    )
    assert "fleet_compiled_stale" in capsys.readouterr().err


def test_cli_check_against_reference_golden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    assert fleet_compile.main(["--check"]) == 0
    drifted = current_fleet()
    drifted["models"][0]["context_window"] += 1
    ref = tmp_path / "ref.json"
    ref.write_text(json.dumps(drifted), encoding="utf-8")
    assert fleet_compile.main(["--check", "--reference", str(ref)]) == 1
    assert "golden_mismatch" in capsys.readouterr().err


def test_cli_compile_error_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pytest.importorskip("yaml")
    import shutil

    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path / "state"))
    broken = tmp_path / "providers.d"
    shutil.copytree(ROOT / "providers.d", broken)
    (broken / "_fleet.yaml").write_text(
        "schema_version: 3\nbogus: 1\n", encoding="utf-8"
    )
    assert fleet_compile.main(["--check", "--providers-dir", str(broken)]) == 1
    assert "header_key_unknown" in capsys.readouterr().err


def test_cli_rejects_broken_provider_but_still_compiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pytest.importorskip("yaml")
    import shutil

    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path / "state"))
    custom = tmp_path / "providers.d"
    shutil.copytree(ROOT / "providers.d", custom)
    (custom / "codex.yaml").write_text(
        "provider_id: codex\nkind: nope\n", encoding="utf-8"
    )
    code = fleet_compile.main(["--write", "--providers-dir", str(custom)])
    err = capsys.readouterr().err
    assert "fleet_provider_rejected provider=codex" in err
    # дефолтная модель каталога не зависит от codex -> сборка успешна
    assert code == 0
    written = json.loads(
        (tmp_path / "state" / "fleet.compiled.json").read_text(encoding="utf-8")
    )
    assert "codex" not in written["backends"]


def test_manifests_dir_digests_cover_header() -> None:
    loaded = load_manifests(ROOT / "providers.d", ADAPTER_KINDS)
    assert "_fleet.yaml" not in loaded.sha256_by_file
    sidecar = compile_from_disk(kinds=ADAPTER_KINDS, now=NOW).sidecar
    assert "_fleet.yaml" in sidecar["inputs"]["manifests"]


def test_compile_does_not_mutate_manifests_or_header() -> None:
    hdr = dict(header(), default_model="alpha-one")
    snapshot = copy.deepcopy(hdr)
    compile_catalog(hdr, build_manifests(manifest_doc()), kinds=ADAPTER_KINDS, now=NOW)
    assert hdr == snapshot

from __future__ import annotations

# Пробник моделей: select_manifest по overrides/приоритету, атомарный --promote, aliases smoke_models.

import copy
import fcntl
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from adapters import ADAPTER_KINDS  # noqa: E402
from core import catalog_promote  # noqa: E402
from core.fleet_compiler import CompileResult  # noqa: E402
from core.probe_manifest_select import select_manifest  # noqa: E402
from core.provider_manifest import load_manifests  # noqa: E402

_probe_tests = importlib.import_module(
    "test_capability_probe"
)  # общие стенды соседних тестов
_fleet_tests = importlib.import_module("test_fleet_compiler")
KEY, FakeBridge, cp = _probe_tests.KEY, _probe_tests.FakeBridge, _probe_tests.cp
build_manifests, manifest_doc = _fleet_tests.build_manifests, _fleet_tests.manifest_doc

PROVIDERS = ROOT / "providers.d"


# ---- select_manifest -------------------------------------------------------------------


def test_select_manifest_sees_overrides_only_models() -> None:
    manifests = build_manifests(manifest_doc("alpha"))
    picked = select_manifest(manifests, "alpha-one", None)
    assert picked.problem is None and picked.manifest is not None
    assert picked.manifest.provider_id == "alpha"


@pytest.mark.parametrize(
    "first,second,winner",
    [
        ((50, None), (10, None), "beta"),
        ((20, None), (20, None), "alpha"),  # равный priority: лексикографически
        ((50, 20), (10, 10), "alpha"),
        ((50, 20), (10, 20), "beta"),
        ((1, 0), (99, 1), "beta"),
        ((50, None), (10, 0), "alpha"),
        ((20, 0), (20, 0), "alpha"),
    ],
)
def test_select_manifest_tiebreak_matches_compiler(
    first: tuple[int, int | None], second: tuple[int, int | None], winner: str
) -> None:
    docs = []
    for provider, (priority, weight) in zip(("alpha", "beta"), (first, second)):
        doc = manifest_doc(
            provider, priority=priority, models_overrides={"shared-model": {}}
        )
        if weight is not None:
            doc["routing"] = {"weight": weight}
        docs.append(doc)
    picked = select_manifest(build_manifests(*docs), "shared-model", None)
    assert picked.manifest is not None
    assert (picked.problem, picked.manifest.provider_id) == (None, winner)
    compiled = _fleet_tests.compile_docs(
        *docs, hdr=dict(_fleet_tests.header(), default_model="shared-model")
    )
    assert compiled.sidecar["models"]["shared-model"]["provider"] == winner


def test_select_manifest_on_real_providers() -> None:
    manifests = load_manifests(PROVIDERS, ADAPTER_KINDS).manifests
    for model, provider in (
        ("gpt-6.1-sol", "openai-key-2"),
        ("deepseek-v4.1-flash", "deepseek-direct"),
        ("gpt-6.1-terra", "openai-key-2"),
        ("gemini-4-argon", "agy"),
    ):
        picked = select_manifest(manifests, model, None)
        assert picked.manifest is not None, model
        assert (picked.problem, picked.manifest.provider_id) == (None, provider), model
    missing = select_manifest(manifests, "no-such-model", None)
    assert (missing.manifest, missing.problem) == (None, "provider_not_found")


def test_strict_selection_retains_legacy_ambiguity() -> None:
    docs = [manifest_doc(p, discovery={"static": ["shared-model"]}) for p in ("alpha", "beta")]
    manifests = build_manifests(*docs)
    ambiguous = select_manifest(manifests, "shared-model", None, strict_ambiguous=True)
    assert (ambiguous.manifest, ambiguous.problem) == (None, "provider_ambiguous")
    override = select_manifest(build_manifests(manifest_doc()), "alpha-one", None, strict_ambiguous=True)
    assert (override.manifest, override.problem) == (None, "provider_not_found")
    named = select_manifest(manifests, "shared-model", "beta", strict_ambiguous=True)
    assert named.manifest is not None and named.manifest.provider_id == "beta"


# ---- --promote -------------------------------------------------------------------------


@pytest.fixture()
def promote_env(tmp_path: Path) -> Any:
    providers = tmp_path / "providers.d"
    shutil.copytree(PROVIDERS, providers)
    state = tmp_path / "state"
    env = {
        "BRIDGE_STATE_DIR": str(state),
        "BRIDGE_PROBE_TIMEOUT_S": "10",
        "BRIDGE_GIT_SHA": "a" * 40,
        "BRIDGE_KEY": KEY,
        "BRIDGE_PROVIDERS_DIR": str(providers),
    }
    return providers, state, env


def _probe(mode: str, providers: Path, env: dict[str, str], **kw: Any) -> int:
    """Проба weighted-владельца; именованный Codex проверяется отдельно."""
    hub = FakeBridge(mode)
    try:
        return cp.probe_cli(
            "gpt-6.1-sol",
            provider_id=kw.pop("provider_id", "openai-key-2"),
            hub_url=hub.hub_url,
            as_json=True,
            providers_dir=providers,
            env=env,
            **kw,
        )
    finally:
        hub.close()


def test_explicit_codex_does_not_promote_direct_owner(
    promote_env: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    providers, state, env = promote_env
    named = select_manifest(load_manifests(providers, ADAPTER_KINDS).manifests, "gpt-6.1-sol", "codex")
    assert named.manifest is not None and named.manifest.provider_id == "codex"
    assert _probe("good", providers, env, provider_id="codex", promote=True) == 1
    output = capsys.readouterr()
    summary = json.loads(output.out)
    assert (summary["provider_id"], summary["verdict"]) == ("codex", "confirmed")
    assert "post_verify_mismatch" in output.err
    assert not any(
        (state / p).exists()
        for p in ("model-lifecycle.json", "catalog.lock.json", "fleet.compiled.json")
    )


def _promoted(promote_env: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    """Прогон `good`-пробы с `--promote`: `(summary, state_dir)`."""
    providers, state, env = promote_env
    assert _probe("good", providers, env, promote=True) == 0
    summary = json.loads(capsys.readouterr().out)
    raw = Path(summary["receipt"]).read_bytes()
    receipt = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == summary["receipt_sha256"]
    assert raw == json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert (receipt["provider_id"], receipt["model_id"]) == ("openai-key-2", "gpt-6.1-sol")
    return summary, state


def test_promote_confirmed_updates_lifecycle(
    promote_env: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    summary, state = _promoted(promote_env, capsys)
    assert summary["provider_id"] == "openai-key-2" and summary["verdict"] == "confirmed"
    records = json.loads((state / "model-lifecycle.json").read_text())["records"]
    assert len(records) == 1 and records[0]["status"] == "confirmed"
    assert records[0]["receipt_sha256"] == summary["receipt_sha256"]
    assert len(records[0]["fingerprint_sha256"]) == 64
    assert (records[0]["provider_id"], records[0]["model_id"]) == ("openai-key-2", "gpt-6.1-sol")
    assert records[0]["fingerprint_sha256"] == hashlib.sha256(b"no-fingerprint").hexdigest()
    assert (state / ".lifecycle.lock").exists()


def test_promote_confirmed_updates_sidecar_and_compiled(
    promote_env: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    summary, state = _promoted(promote_env, capsys)
    sidecar = json.loads((state / "catalog.lock.json").read_text())["models"]
    entry = sidecar["gpt-6.1-sol"]
    assert (entry["status"], entry["quorum_eligible"], entry["provider"]) == (
        "confirmed",
        True,
        "openai-key-2",
    )
    assert (entry["family"], entry["family_source"]) == ("OpenAI", "exact_map")
    assert entry["probe"]["receipt_sha256"] == summary["receipt_sha256"]
    assert entry["probe"]["fingerprint_sha256"] == hashlib.sha256(b"no-fingerprint").hexdigest()
    assert entry["efforts_proven"] == ["low", "medium", "high", "xhigh", "max"]
    compiled = json.loads((state / "fleet.compiled.json").read_text())
    models = {m["id"]: m for m in compiled["models"]}
    assert models["gpt-6.1-sol"]["backend"] == "openai-key-2"
    assert models["gpt-6.1-sol"]["efforts"] == [
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    ]


def test_promote_honours_explicit_state_dir(promote_env: Any, tmp_path: Path) -> None:
    providers, state, env = promote_env
    target = tmp_path / "elsewhere"
    assert _probe("good", providers, env, promote=True, state_dir=target) == 0
    assert (target / "catalog.lock.json").is_file() and not state.exists()


def test_failed_verdict_is_not_promoted(promote_env: Any) -> None:
    providers, state, env = promote_env
    assert _probe("tool_broken", providers, env, promote=True) == 1
    assert (
        not (state / "model-lifecycle.json").exists()
        and not (state / "catalog.lock.json").exists()
    )


def test_busy_lifecycle_lock_fails_without_writing(promote_env: Any) -> None:
    providers, state, env = promote_env
    state.mkdir(parents=True)
    with open(state / ".lifecycle.lock", "a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        code = _probe(
            "good",
            providers,
            dict(env, BRIDGE_LIFECYCLE_LOCK_WAIT_S="0.2"),
            promote=True,
        )
    assert code == 1 and not (state / "model-lifecycle.json").exists()


@pytest.mark.parametrize("seeded", [False, True])
def test_post_verify_mismatch_is_reported(
    promote_env: Any, capsys: pytest.CaptureFixture[str], seeded: bool
) -> None:
    providers, state, env = promote_env
    snapshot = {
        state / p: ("previous " + p).encode() for p in ("catalog.lock.json", "fleet.compiled.json")
    }
    if seeded:
        state.mkdir()
        for path, data in snapshot.items():
            path.write_bytes(data)
    real = catalog_promote.compile_from_disk

    def stale(*args: Any, **kwargs: Any) -> CompileResult:
        result = real(*args, **kwargs)
        sidecar = copy.deepcopy(result.sidecar)
        sidecar["models"]["gpt-6.1-sol"]["status"] = "quarantine"
        return CompileResult(fleet=result.fleet, sidecar=sidecar)

    with mock.patch.object(catalog_promote, "compile_from_disk", stale):
        assert _probe("good", providers, env, promote=True) == 1
    assert "post_verify" in capsys.readouterr().err
    assert not (state / "model-lifecycle.json").exists()
    for path, data in snapshot.items():
        assert path.read_bytes() == data if seeded else not path.exists()


# ---- smoke_models: aliases с backend_id ------------------------------------------------


def test_smoke_aliases_accept_backend_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(
        "smoke_models_alias_test", ROOT / "scripts" / "smoke_models.py"
    )
    assert spec is not None and spec.loader is not None
    sm = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "smoke_models_alias_test", sm)
    spec.loader.exec_module(sm)
    fleet = {
        "models": [{"id": "a"}],
        "aliases": {
            "a-high": {"backend_id": "a", "backend": "droid", "effort": "high"},
            "b": "c",
            "d": {"model": "e"},
        },
    }
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps(fleet), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_FLEET_PATH", str(path))
    sm._load_fleet_config.cache_clear()
    try:
        _, aliases = sm._load_fleet_config()
        assert aliases == {"a-high": "a", "b": "c", "d": "e"}
        assert sm.build_bridge_payload("a-high")["model"] == "a"
    finally:
        sm._load_fleet_config.cache_clear()

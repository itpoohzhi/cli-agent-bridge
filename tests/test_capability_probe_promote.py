from __future__ import annotations

# Пробник моделей: select_manifest по overrides/приоритету, атомарный --promote, aliases smoke_models.

import copy
import fcntl
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


def _winner(*docs: Any) -> str | None:
    picked = select_manifest(build_manifests(*docs), "shared-model", None)
    assert picked.problem is None and picked.manifest is not None
    return picked.manifest.provider_id


def test_select_manifest_tiebreak_matches_compiler() -> None:
    shared = {"shared-model": {}}
    cases = [
        (dict(priority=50), dict(priority=10), "beta"),
        (
            dict(priority=20),
            dict(priority=20),
            "alpha",
        ),  # равный priority: лексикографически
    ]
    for first, second, winner in cases:
        docs = [
            manifest_doc("alpha", models_overrides=shared, **first),
            manifest_doc("beta", models_overrides=shared, **second),
        ]
        assert _winner(*docs) == winner


def test_select_manifest_on_real_providers() -> None:
    manifests = load_manifests(PROVIDERS, ADAPTER_KINDS).manifests
    for model, provider in (
        ("gpt-6.1-sol", "codex"),
        ("deepseek-v4.1-flash", "opencode-go"),
        ("gpt-6.1-terra", "codex"),
        ("gemini-4-argon", "agy"),
    ):
        picked = select_manifest(manifests, model, None)
        assert picked.manifest is not None, model
        assert (picked.problem, picked.manifest.provider_id) == (None, provider), model
    named = select_manifest(manifests, "gpt-6.1-sol", "codex")
    assert named.manifest is not None and named.manifest.provider_id == "codex"
    missing = select_manifest(manifests, "no-such-model", None)
    assert (missing.manifest, missing.problem) == (None, "provider_not_found")


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
    hub = FakeBridge(mode)
    try:
        return cp.probe_cli(
            "gpt-6.1-sol",
            hub_url=hub.hub_url,
            as_json=True,
            providers_dir=providers,
            env=env,
            **kw,
        )
    finally:
        hub.close()


def _promoted(promote_env: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    """Прогон `good`-пробы с `--promote`: `(summary, state_dir)`."""
    providers, state, env = promote_env
    assert _probe("good", providers, env, promote=True) == 0
    return json.loads(capsys.readouterr().out), state


def test_promote_confirmed_updates_lifecycle(
    promote_env: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    summary, state = _promoted(promote_env, capsys)
    assert summary["provider_id"] == "codex" and summary["verdict"] == "confirmed"
    records = json.loads((state / "model-lifecycle.json").read_text())["records"]
    assert len(records) == 1 and records[0]["status"] == "confirmed"
    assert records[0]["receipt_sha256"] == summary["receipt_sha256"]
    assert len(records[0]["fingerprint_sha256"]) == 64
    assert (state / ".lifecycle.lock").exists()


def test_promote_confirmed_updates_sidecar_and_compiled(
    promote_env: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    _, state = _promoted(promote_env, capsys)
    sidecar = json.loads((state / "catalog.lock.json").read_text())["models"]
    entry = sidecar["gpt-6.1-sol"]
    assert (entry["status"], entry["quorum_eligible"], entry["provider"]) == (
        "confirmed",
        True,
        "codex",
    )
    compiled = json.loads((state / "fleet.compiled.json").read_text())
    efforts = {m["id"]: m["efforts"] for m in compiled["models"]}
    assert efforts["gpt-6.1-sol"] == [
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


def test_post_verify_mismatch_is_reported(
    promote_env: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    providers, state, env = promote_env
    real = catalog_promote.compile_from_disk

    def stale(*args: Any, **kwargs: Any) -> CompileResult:
        result = real(*args, **kwargs)
        sidecar = copy.deepcopy(result.sidecar)
        sidecar["models"]["gpt-6.1-sol"]["status"] = "quarantine"
        return CompileResult(fleet=result.fleet, sidecar=sidecar)

    with mock.patch.object(catalog_promote, "compile_from_disk", stale):
        assert _probe("good", providers, env, promote=True) == 1
    assert "post_verify" in capsys.readouterr().err


# ---- smoke_models: aliases с backend_id ------------------------------------------------


def test_smoke_aliases_accept_backend_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(
        "smoke_models_alias_test", ROOT / "scripts" / "smoke_models.py"
    )
    assert spec is not None and spec.loader is not None
    sm = importlib.util.module_from_spec(spec)
    sys.modules["smoke_models_alias_test"] = sm
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

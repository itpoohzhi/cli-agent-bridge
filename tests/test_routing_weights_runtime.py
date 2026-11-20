"""Тесты рантайм-кэша и атомарного хранилища оперативных весов маршрутизации."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from core import routing_weights_runtime as rwr
from core.routing_contract import routes_catalog_hash
from core.routing_weights_domain import WeightsOverrideDoc


def _write_v1(path: Path, providers: dict[str, int] | None = None, models: dict[str, dict[str, int]] | None = None) -> None:
    payload = {
        "schema_version": 1,
        "updated_at": "2026-11-20T20:00:00Z",
        "updated_by": "test",
        "providers": providers or {},
        "models": models or {},
    }
    _ = path.write_text(json.dumps(payload), encoding="utf-8")


def _sample_model() -> dict[str, Any]:
    routes = [
        {"route_id": "codex", "backend": "codex", "weight": 20, "priority": 10},
        {"route_id": "openai-key-3", "backend": "openai-key-3", "weight": 80, "priority": 20},
    ]
    return {
        "id": "gpt-6.1-sol",
        "backend": "openai-key-3",
        "routing": {
            "algorithm": "weighted-sha256-v1",
            "enabled": True,
            "catalog_hash": routes_catalog_hash(routes),
            "legacy_backend": "openai-key-3",
            "disabled_backend": "codex",
            "routes": routes,
        },
    }


def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    dyn_cfg = tmp_path / "dynamic_config.json"
    weights_path = tmp_path / "routing_weights.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(dyn_cfg))
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_PATH", str(weights_path))
    rwr._DEFAULT_CACHE.invalidate()
    return weights_path


def test_cache_hit_within_ttl_and_hot_reload_after_ttl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Кэш-хит внутри TTL обходится без sys-вызовов, а по истечении TTL подхватывает правку."""
    weights = _isolated_env(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_TTL_S", "5.0")
    _write_v1(weights, providers={"codex": 25})

    now = [100.0]
    monkeypatch.setattr(rwr.time, "monotonic", lambda: now[0])
    cache = rwr.RoutingWeightsCache()

    doc1 = cache.get_doc(weights)
    assert doc1 is not None and doc1.providers == {"codex": 25}

    _write_v1(weights, providers={"codex": 90})
    now[0] = 104.0
    with monkeypatch.context() as mp:
        mp.setattr(os, "lstat", lambda _p: (_ for _ in ()).throw(AssertionError("lstat запрещён внутри TTL")))
        assert cache.get_doc(weights) is doc1

    now[0] = 106.0
    doc3 = cache.get_doc(weights)
    assert doc3 is not None and doc3.providers == {"codex": 90}

    # Неизменённая stat-подпись после очередного TTL не вызывает повторный os.open.
    now[0] = 112.0
    with monkeypatch.context() as mp:
        mp.setattr(os, "open", lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("os.open запрещён")))
        assert cache.get_doc(weights) is doc3


def test_cache_missing_file_returns_none_without_noise(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Отсутствие файла весов возвращает None без предупреждений в stderr."""
    weights = _isolated_env(monkeypatch, tmp_path)
    assert rwr.RoutingWeightsCache().get_doc(weights) is None
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("case", ["corrupt_json", "invalid_schema", "exceeds_max_bytes", "symlink"])
def test_cache_fail_closed_and_rate_limited_stderr(
    case: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """При битом JSON, неверной схеме, превышении max_bytes и симлинке кэш отдаёт None и пишет в stderr."""
    weights = _isolated_env(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_TTL_S", "0.0")
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_LOG_INTERVAL_S", "30.0")
    now = [200.0]
    monkeypatch.setattr(rwr.time, "monotonic", lambda: now[0])

    if case == "corrupt_json":
        _ = weights.write_text("{broken", encoding="utf-8")
    elif case == "invalid_schema":
        _ = weights.write_text(json.dumps({"schema_version": 2, "providers": {}, "models": {}}), encoding="utf-8")
    elif case == "exceeds_max_bytes":
        monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_MAX_BYTES", "1024")
        _write_v1(weights, providers={"codex": 50}, models={"m": {f"b{i}": 10 for i in range(120)}})
    elif case == "symlink":
        target = tmp_path / "real.json"
        _write_v1(target, providers={"codex": 77})
        weights.symlink_to(target)

    cache = rwr.RoutingWeightsCache()
    assert cache.get_doc(weights) is None
    assert "fail-closed" in capsys.readouterr().err

    # Повторный отказ внутри LOG_INTERVAL_S не спамит, а после интервала пишет снова.
    now[0] = 210.0
    if case == "corrupt_json":
        _ = weights.write_text("{broken-again", encoding="utf-8")
        assert cache.get_doc(weights) is None
        assert capsys.readouterr().err == ""
        now[0] = 235.0
        _ = weights.write_text("{broken-after-interval", encoding="utf-8")
        assert cache.get_doc(weights) is None
        assert "fail-closed" in capsys.readouterr().err


def test_disabled_flag_and_corrupt_dynamic_config_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """BRIDGE_ROUTING_WEIGHTS_ENABLED=false и битый dynamic_config.json отключают overrides."""
    weights = _isolated_env(monkeypatch, tmp_path)
    _write_v1(weights, providers={"codex": 95})
    dyn_cfg = Path(os.environ["BRIDGE_DYNAMIC_CONFIG_PATH"])

    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_ENABLED", "false")
    cache = rwr.RoutingWeightsCache()
    assert cache.get_doc(weights) is None

    monkeypatch.delenv("BRIDGE_ROUTING_WEIGHTS_ENABLED")
    _ = dyn_cfg.write_text("{broken-dynamic-config", encoding="utf-8")
    assert cache.get_doc(weights) is None

    _ = dyn_cfg.write_text(json.dumps({"BRIDGE_ROUTING_WEIGHTS_ENABLED": True}), encoding="utf-8")
    cache.invalidate(weights)
    assert cache.get_doc(weights) is not None


def test_store_mutate_atomic_permissions_and_rejects_corrupt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """RoutingWeightsStore.mutate пишет атомарно с правами 0600 и отказывает на битом файле."""
    weights = _isolated_env(monkeypatch, tmp_path)
    nested = tmp_path / "cfg" / "routing_weights.json"
    store = rwr.RoutingWeightsStore()

    doc = store.mutate(
        nested,
        lambda cur: {
            **cur.to_dict(),
            "updated_by": "pytest",
            "models": {"gpt-6.1-sol": {"codex": 70, "openai-key-3": 30}},
        },
    )
    assert doc.models["gpt-6.1-sol"] == {"codex": 70, "openai-key-3": 30}
    assert stat.S_IMODE(nested.stat().st_mode) == 0o600
    assert stat.S_IMODE(nested.parent.stat().st_mode) == 0o700
    assert store.load_strict(nested).models["gpt-6.1-sol"]["codex"] == 70

    _ = weights.write_text("{corrupt", encoding="utf-8")
    with pytest.raises(rwr.WeightsCorruptError):
        _ = store.mutate(weights, lambda cur: cur)
    assert weights.read_text(encoding="utf-8") == "{corrupt"

    sym = tmp_path / "sym.json"
    sym.symlink_to(nested)
    with pytest.raises(rwr.WeightsCorruptError):
        _ = store.load_strict(sym)


def test_store_repair_archives_corrupt_and_symlink(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """repair переносит битый файл или симлинк в .corrupt (с уникальным суффиксом) и создаёт пустой v1."""
    weights = _isolated_env(monkeypatch, tmp_path)
    store = rwr.RoutingWeightsStore()

    _ = weights.write_text("{bad1", encoding="utf-8")
    backup1 = store.repair(weights)
    assert backup1 == weights.with_name("routing_weights.json.corrupt")
    assert backup1.read_text(encoding="utf-8") == "{bad1"
    assert stat.S_IMODE(weights.stat().st_mode) == 0o600
    assert store.load_strict(weights) == WeightsOverrideDoc.empty()

    _ = weights.write_text("{bad2", encoding="utf-8")
    backup2 = store.repair(weights)
    assert backup2 != backup1
    assert backup2.name.startswith("routing_weights.json.corrupt.")
    assert backup1.read_text(encoding="utf-8") == "{bad1"
    assert backup2.read_text(encoding="utf-8") == "{bad2"

    real_target = tmp_path / "real_target.json"
    _write_v1(real_target, providers={"codex": 44})
    sym = tmp_path / "link_weights.json"
    sym.symlink_to(real_target)
    sym_backup = store.repair(sym)
    assert sym_backup.is_symlink()
    assert not sym.is_symlink()
    assert store.load_strict(real_target).providers == {"codex": 44}
    assert store.load_strict(sym) == WeightsOverrideDoc.empty()


def test_store_flock_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Занятый flock приводит к WeightsLockTimeoutError без изменения целевого файла."""
    weights = _isolated_env(monkeypatch, tmp_path)
    _write_v1(weights, providers={"codex": 15})
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_LOCK_WAIT_S", "0.1")
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_LOCK_POLL_S", "0.01")

    lock_file = weights.parent / ".routing_weights.json.lock"
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    store = rwr.RoutingWeightsStore()
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(rwr.WeightsLockTimeoutError):
            _ = store.mutate(weights, lambda cur: {**cur.to_dict(), "providers": {"codex": 99}})
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert store.load_strict(weights).providers == {"codex": 15}


def test_effective_model_routing_applies_and_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """effective_model_routing применяет overrides и откатывается к base при отсутствии/сбое файла."""
    weights = _isolated_env(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_TTL_S", "0.0")
    model = _sample_model()

    assert rwr.effective_model_routing("gpt-6.1-sol", model) == model["routing"]
    singleton = rwr.base_model_routing({"backend": "codex"})
    assert singleton is not None and singleton["routes"][0]["backend"] == "codex"
    assert rwr.base_model_routing({}) == {}

    _write_v1(weights, models={"gpt-6.1-sol": {"codex": 90, "openai-key-3": 10}})
    eff = rwr.effective_model_routing("gpt-6.1-sol", model)
    assert eff is not None
    assert {r["backend"]: r["weight"] for r in eff["routes"]} == {"codex": 90, "openai-key-3": 10}
    assert eff["legacy_backend"] == "codex"

    _ = weights.write_text("{corrupt", encoding="utf-8")
    assert rwr.effective_model_routing("gpt-6.1-sol", model) == model["routing"]
    # enabled: False маршрут игнорируется при выборе legacy_backend, если есть включённые.
    _write_v1(weights, models={"gpt-6.1-sol": {"codex": 99, "openai-key-3": 1}})
    disabled_model = _sample_model()
    disabled_model["routing"]["routes"][0]["enabled"] = False
    rwr._DEFAULT_CACHE.invalidate()
    eff_dis = rwr.effective_model_routing("gpt-6.1-sol", disabled_model)
    assert eff_dis is not None and eff_dis["legacy_backend"] == "openai-key-3"


@pytest.mark.parametrize("env_key", ["BRIDGE_ROUTING_WEIGHTS_TTL_S", "BRIDGE_ROUTING_WEIGHTS_MAX_BYTES", "BRIDGE_ROUTING_WEIGHTS_LOG_INTERVAL_S"])
def test_bad_numeric_config_fail_closed_in_hot_path(
    env_key: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-015: битые числовые параметры не бросают ConfigError/ValueError, а откатываются к base."""
    weights = _isolated_env(monkeypatch, tmp_path)
    _ = weights.write_text("{corrupt", encoding="utf-8") if env_key == "BRIDGE_ROUTING_WEIGHTS_LOG_INTERVAL_S" else _write_v1(weights, models={"gpt-6.1-sol": {"codex": 95, "openai-key-3": 5}})
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_TTL_S", "0.0")
    monkeypatch.setenv(env_key, "not-a-number")
    model = _sample_model()

    assert rwr.effective_model_routing("gpt-6.1-sol", model) == model["routing"]
    assert "fail-closed" in capsys.readouterr().err
    assert rwr.effective_model_routing("gpt-6.1-sol", model) == model["routing"]
    assert capsys.readouterr().err == ""

    monkeypatch.delenv(env_key, raising=False)
    Path(os.environ["BRIDGE_DYNAMIC_CONFIG_PATH"]).write_text(json.dumps({env_key: "not-a-number"}), encoding="utf-8")
    rwr._DEFAULT_CACHE.invalidate()
    assert rwr.effective_model_routing("gpt-6.1-sol", model) == model["routing"]

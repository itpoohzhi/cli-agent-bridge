"""Adversarial, concurrency и purity тесты подсистемы оперативных весов маршрутизации."""

from __future__ import annotations

import ast
import importlib
import json
import stat
import threading
from pathlib import Path
from typing import Any

import pytest

from core import routing_weights_runtime as rwr
from core.routing_weights_domain import (
    WeightsValidationError,
    build_catalog_routing_view,
    validate_weights_document,
)
from core.transport_routing import route_order
from tools import routing_weights as rw

ROOT = Path(__file__).resolve().parents[1]
REAL_FLEET = ROOT / "fleet.json"
_FORBIDDEN_DOMAIN_IMPORTS = frozenset({
    "os", "sys", "pathlib", "io", "fcntl", "tempfile", "subprocess", "socket",
    "urllib", "http", "json", "threading", "multiprocessing", "time", "shutil",
    "core.runtime_env", "core.routing_weights_runtime",
})
_MUTABLE_NAMES = frozenset({"dict", "list", "set", "bytearray", "defaultdict", "deque"})


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Изолирует пути dynamic_config и routing_weights внутри tmp_path."""
    dyn_cfg = tmp_path / "dynamic_config.json"
    weights_path = tmp_path / "routing_weights.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(dyn_cfg))
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_PATH", str(weights_path))
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_TTL_S", "0.0")
    rwr._DEFAULT_CACHE.invalidate()
    return weights_path


def _fleet_models() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Загружает реальный fleet.json и индексирует модели по id."""
    fleet = json.loads(REAL_FLEET.read_text(encoding="utf-8"))
    return fleet, {m["id"]: m for m in fleet["models"]}


def _apply_worker_update(cur: Any, idx: int) -> dict[str, Any]:
    """Обновляет отдельную модель или провайдера для потока idx."""
    payload = cur.to_dict()
    payload["updated_by"] = f"worker-{idx}"
    if idx % 2 == 0:
        payload["models"][f"model-{idx}"] = {"codex": 100 + idx}
    else:
        payload["providers"][f"prov-{idx}"] = 200 + idx
    return payload


def _mutate_worker(
    idx: int, barrier: threading.Barrier, store: rwr.RoutingWeightsStore, errors: list[BaseException],
) -> None:
    """Выполняет синхронизированную барьером мутацию из отдельного потока."""
    try:
        barrier.wait(timeout=5.0)
        _ = store.mutate(None, lambda cur: _apply_worker_update(cur, idx))
    except BaseException as exc:  # noqa: BLE001
        errors.append(exc)


def test_concurrent_mutate_flock_no_lost_updates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """8 параллельных потоков одновременно мутируют один файл без потерь и с правами 0600."""
    weights = _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_LOCK_WAIT_S", "15.0")
    store = rwr.RoutingWeightsStore(weights)
    barrier, errors = threading.Barrier(8), []
    threads = [threading.Thread(target=_mutate_worker, args=(i, barrier, store, errors)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15.0)

    assert not errors
    doc = validate_weights_document(json.loads(weights.read_text(encoding="utf-8")))
    assert all(doc.models[f"model-{i}"] == {"codex": 100 + i} for i in range(0, 8, 2))
    assert all(doc.providers[f"prov-{i}"] == 200 + i for i in range(1, 8, 2))
    assert stat.S_IMODE(weights.stat().st_mode) == 0o600


def test_symlink_attack_etc_passwd_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Симлинк на /etc/passwd возвращает None без утечки содержимого и блокирует mutate."""
    passwd_path = Path("/etc/passwd")
    if not passwd_path.exists():
        pytest.skip("/etc/passwd отсутствует")
    weights = _isolate(monkeypatch, tmp_path)
    weights.symlink_to(passwd_path)
    assert rwr.RoutingWeightsCache().get_doc(weights) is None
    err = capsys.readouterr().err
    assert "fail-closed" in err and "root:" not in err
    with pytest.raises(rwr.WeightsCorruptError):
        _ = rwr.RoutingWeightsStore().mutate(weights, lambda cur: cur)


def test_symlink_attack_preserves_temp_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Симлинк на временный файл отсекается O_NOFOLLOW без перезаписи целевого файла."""
    weights = _isolate(monkeypatch, tmp_path)
    victim = tmp_path / "victim.json"
    sentinel = '{"secret": "untouched-target"}'
    _ = victim.write_text(sentinel, encoding="utf-8")
    weights.symlink_to(victim)

    assert rwr.RoutingWeightsCache().get_doc(weights) is None
    assert "untouched-target" not in capsys.readouterr().err
    with pytest.raises(rwr.WeightsCorruptError):
        _ = rwr.RoutingWeightsStore().mutate(weights, lambda cur: {**cur.to_dict(), "providers": {"codex": 50}})
    assert weights.is_symlink() and victim.read_text(encoding="utf-8") == sentinel


def test_real_fleet_hot_path_distribution_and_zero_reserve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """На реальном fleet.json claude-haiku-5-5 держит 80/20 долю и переходит в резерв при 0/100."""
    weights = _isolate(monkeypatch, tmp_path)
    _, models = _fleet_models()
    haiku = models["claude-haiku-5-5"]

    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-model", "claude-haiku-5-5", "claude-p=80", "opencode-go-claude=20", "--json"]) == 0
    rwr._DEFAULT_CACHE.invalidate()
    eff = rwr.effective_model_routing("claude-haiku-5-5", haiku)
    assert eff is not None
    eff_haiku = {**haiku, "routing": eff}
    claude_hits = sum(1 for i in range(500) if next(route_order("claude-haiku-5-5", eff_haiku, f"seed-{i}")) == "claude-p")
    assert 350 <= claude_hits <= 450

    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-model", "claude-haiku-5-5", "claude-p=0", "opencode-go-claude=100", "--json"]) == 0
    rwr._DEFAULT_CACHE.invalidate()
    eff_zero = rwr.effective_model_routing("claude-haiku-5-5", haiku)
    assert eff_zero is not None
    eff_haiku_zero = {**haiku, "routing": eff_zero}
    assert {tuple(route_order("claude-haiku-5-5", eff_haiku_zero, f"zero-{i}")) for i in range(50)} == {("opencode-go-claude", "claude-p")}


def test_real_fleet_model_override_beats_provider_without_bleed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Per-model override для claude-haiku-5-5 побеждает provider=0, не меняя sonnet/opus."""
    weights = _isolate(monkeypatch, tmp_path)
    fleet, models = _fleet_models()
    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-provider", "claude-p", "0", "--json"]) == 0
    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-model", "claude-haiku-5-5", "claude-p=80", "--json"]) == 0
    rwr._DEFAULT_CACHE.invalidate()

    doc = rwr.RoutingWeightsStore(weights).load_strict()
    view = build_catalog_routing_view(fleet, doc)
    haiku_routes = {r["backend"]: r for r in view["models"]["claude-haiku-5-5"]["routes"]}
    assert (haiku_routes["claude-p"]["weight"], haiku_routes["claude-p"]["source"]) == (80, "model-override")
    assert view["models"]["claude-sonnet-5-5"]["routes"][0]["weight"] == 0
    assert view["models"]["claude-opus-5-5"]["routes"][0]["weight"] == 0
    eff_sonnet = rwr.effective_model_routing("claude-sonnet-5-5", models["claude-sonnet-5-5"])
    assert eff_sonnet is not None and eff_sonnet["routes"][0]["weight"] == 0


@pytest.mark.parametrize(
    ("model_id", "assignments", "expected_first"),
    [
        ("gpt-6.1-sol", ["codex=100", "openai-key-3=0"], "codex"),
        ("gpt-6.1-terra", ["codex=0", "openai-key-3=100"], "openai-key-3"),
        ("deepseek-v4.1-flash", ["neuralwatt=0", "deepseek-direct=100", "opencode-go=0"], "deepseek-direct"),
    ],
)
def test_real_fleet_multi_route_models_hot_path(
    model_id: str, assignments: list[str], expected_first: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Горячий путь effective_model_routing + route_order работает на всех multi-route моделях fleet.json."""
    weights = _isolate(monkeypatch, tmp_path)
    _, models = _fleet_models()
    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-model", model_id, *assignments, "--json"]) == 0
    rwr._DEFAULT_CACHE.invalidate()
    eff = rwr.effective_model_routing(model_id, models[model_id])
    assert eff is not None
    assert next(route_order(model_id, {**models[model_id], "routing": eff}, "hot-seed")) == expected_first


def test_max_bytes_limit_rejects_oversized_read_and_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Превышение max_bytes блокирует и чтение (fail-closed), и запись без порчи файла."""
    weights = _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_MAX_BYTES", "1024")
    store, cache = rwr.RoutingWeightsStore(weights), rwr.RoutingWeightsCache()

    base = json.dumps({"schema_version": 1, "updated_at": None, "updated_by": "t", "providers": {"codex": 10}, "models": {}})
    _ = weights.write_text(base + " " * (1024 - len(base)), encoding="utf-8")
    assert cache.get_doc(weights) is not None and store.load_strict(weights).providers == {"codex": 10}

    with pytest.raises(WeightsValidationError):
        _ = store.mutate(weights, lambda cur: {**cur.to_dict(), "models": {"m": {f"b{i}": 1 for i in range(90)}}})
    assert store.load_strict(weights).providers == {"codex": 10}

    _ = weights.write_text(base + " " * (1025 - len(base)), encoding="utf-8")
    assert cache.get_doc(weights) is None
    with pytest.raises(rwr.WeightsCorruptError):
        _ = store.load_strict(weights)
    with pytest.raises(rwr.WeightsCorruptError):
        _ = store.mutate(weights, lambda cur: cur)


@pytest.mark.parametrize("good", [0, 10000])
def test_boundary_valid_weights_domain_store_and_cli(good: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Граничные целые веса 0 и 10000 принимаются доменом, хранилищем и CLI."""
    weights = _isolate(monkeypatch, tmp_path)
    doc = validate_weights_document({"schema_version": 1, "providers": {"codex": good}, "models": {"gpt-6.1-sol": {"codex": good}}})
    assert doc.providers["codex"] == good and doc.models["gpt-6.1-sol"]["codex"] == good
    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-provider", "codex", str(good), "--json"]) == 0
    assert rwr.RoutingWeightsStore(weights).load_strict().providers["codex"] == good


@pytest.mark.parametrize("bad", [10001, -1, True, False])
def test_boundary_invalid_weights_rejected_everywhere(bad: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Недопустимые значения 10001, -1 и bool отвергаются доменом, хранилищем и CLI."""
    weights = _isolate(monkeypatch, tmp_path)
    store = rwr.RoutingWeightsStore(weights)
    with pytest.raises(WeightsValidationError):
        _ = validate_weights_document({"schema_version": 1, "providers": {"codex": bad}, "models": {}})
    with pytest.raises(WeightsValidationError):
        _ = store.mutate(weights, lambda cur: {**cur.to_dict(), "models": {"gpt-6.1-sol": {"codex": bad}}})
    assert rw.main(["--fleet", str(REAL_FLEET), "--weights", str(weights), "set-model", "gpt-6.1-sol", f"codex={bad}", "--json"]) == 1


def _has_mutable_module_value(node: ast.AST) -> bool:
    if isinstance(node, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _MUTABLE_NAMES


def _top_level_values(tree: ast.Module) -> list[ast.AST]:
    out: list[ast.AST] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            out.append(stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            out.append(stmt.value)
    return out


def _assert_domain_imports_pure() -> None:
    tree = ast.parse((ROOT / "core" / "routing_weights_domain.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in _FORBIDDEN_DOMAIN_IMPORTS for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in _FORBIDDEN_DOMAIN_IMPORTS


def test_domain_and_runtime_purity_m_mod_i3_i4() -> None:
    """Проверяет M-MOD-I3 в domain (0 запрещённых импортов) и M-MOD-I4 (0 module-level mutable коллекций)."""
    _assert_domain_imports_pure()
    for mod_name in ("core.routing_weights_domain", "core.routing_weights_runtime"):
        mod_tree = ast.parse((ROOT / f"{mod_name.replace('.', '/')}.py").read_text(encoding="utf-8"))
        assert not any(_has_mutable_module_value(val) for val in _top_level_values(mod_tree))
        mod = importlib.import_module(mod_name)
        assert not any(isinstance(v, (dict, list, set, bytearray)) for k, v in vars(mod).items() if not k.startswith("__"))

"""Тесты CLI tools/routing_weights.py и безопасного rebuild-оркестратора."""
from __future__ import annotations

import io, json, os, stat, subprocess, sys
from pathlib import Path
from typing import Any
import pytest

from core.routing_contract import routes_catalog_hash
from core.routing_weights_runtime import RoutingWeightsStore
from tools import routing_weights as rw


def _sample_fleet() -> dict[str, Any]:
    """Создаёт минимальный валидный fleet.json с multi-route и single-route моделями."""
    routes_sol = [
        {"route_id": "codex", "backend": "codex", "weight": 20, "priority": 10},
        {"route_id": "openai-key-3", "backend": "openai-key-3", "weight": 80, "priority": 20},
    ]
    routes_haiku = [
        {"route_id": "claude-p", "backend": "claude-p", "weight": 50, "priority": 10},
        {"route_id": "opencode-go-claude", "backend": "opencode-go-claude", "weight": 50, "priority": 20},
    ]
    return {
        "schema_version": 3,
        "backends": {
            "codex": {"enabled": True}, "openai-key-3": {"enabled": True},
            "claude-p": {"enabled": True}, "opencode-go-claude": {"enabled": True},
            "droid": {"enabled": False},
        },
        "models": [
            {"id": "gpt-6.1-sol", "backend": "openai-key-3", "routing": {"enabled": True, "catalog_hash": routes_catalog_hash(routes_sol), "routes": routes_sol}},
            {"id": "claude-haiku-5-5", "backend": "claude-p", "routing": {"enabled": True, "catalog_hash": routes_catalog_hash(routes_haiku), "routes": routes_haiku}},
            {"id": "gpt-6.1-terra", "backend": "codex"},
            {"id": "legacy-droid", "backend": "droid"},
        ],
    }


def _env_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Изолирует fleet, lock, weights, dynamic_config и state_dir внутри tmp_path."""
    fleet, lock = tmp_path / "fleet.json", tmp_path / "catalog.lock.json"
    weights, dyn = tmp_path / "routing_weights.json", tmp_path / "dynamic_config.json"
    fleet.write_text(json.dumps(_sample_fleet()), encoding="utf-8")
    lock.write_text(json.dumps({"models": {"gpt-6.1-terra": {"alternates": ["openai-key-3"]}}}), encoding="utf-8")
    dyn.write_text(json.dumps({"BRIDGE_ROUTING_WEIGHTS_ENABLED": True, "BRIDGE_COMPILED_FLEET_ENABLED": False}), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(dyn))
    monkeypatch.setenv("BRIDGE_ROUTING_WEIGHTS_PATH", str(weights))
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path / "state"))
    return fleet, lock, weights, dyn


def _run_cli(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, dict[str, Any]]:
    """Запускает main() и парсит JSON-вывод stdout."""
    capsys.readouterr()
    code = rw.main(argv)
    out = capsys.readouterr().out.strip()
    return code, (json.loads(out) if out else {})


def _mock_urlopen(monkeypatch: pytest.MonkeyPatch, active: int = 0, ok: bool = True) -> None:
    """Подменяет urllib.request.urlopen фейковым ответом /health."""
    body = json.dumps({"ok": ok, "active": active}).encode("utf-8")

    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self
        def __exit__(self, *_a: object) -> None:
            self.close()

    monkeypatch.setattr(rw.urllib.request, "urlopen", lambda *_a, **_kw: _Resp(body))


def test_status_and_mutations_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Проверяет status, set-model, set-provider (affected_models), reset-* и работу без PyYAML."""
    fleet, _, weights, _ = _env_paths(monkeypatch, tmp_path)
    monkeypatch.setitem(sys.modules, "yaml", None)

    code, st0 = _run_cli(capsys, ["--fleet", str(fleet), "status", "--json"])
    assert (code, st0["corrupt"], st0["overrides_count"]) == (0, False, 0)
    assert (st0["weights_enabled"], st0["compiled_fleet_enabled"]) == (True, False)
    assert "gpt-6.1-sol" in st0["categories"]["multi_active"]

    code, sm = _run_cli(capsys, ["--fleet", str(fleet), "--updated-by", "swiftbar", "set-model", "gpt-6.1-sol", "codex=70", "openai-key-3=30", "--json"])
    assert (code, sm["weights"]) == (0, {"codex": 70, "openai-key-3": 30})
    assert _run_cli(capsys, ["--fleet", str(fleet), "status", "--json"])[1]["updated_by"] == "swiftbar"

    code, sp = _run_cli(capsys, ["--fleet", str(fleet), "set-provider", "codex", "15", "--json"])
    assert code == 0
    assert set(sp["affected_models"]) == {"gpt-6.1-sol", "gpt-6.1-terra"}

    code, st1 = _run_cli(capsys, ["--fleet", str(fleet), "status", "--json"])
    assert (code, st1["overrides_count"], st1["updated_by"]) == (0, 3, "cli")
    sol_routes = {r["backend"]: r for r in st1["models"]["gpt-6.1-sol"]["routes"]}
    assert (sol_routes["codex"]["weight"], sol_routes["codex"]["source"]) == (70, "model-override")
    terra_routes = {r["backend"]: r for r in st1["models"]["gpt-6.1-terra"]["routes"]}
    assert (terra_routes["codex"]["weight"], terra_routes["codex"]["source"]) == (15, "provider-override")

    assert _run_cli(capsys, ["--fleet", str(fleet), "reset-model", "gpt-6.1-sol", "--json"])[0] == 0
    assert _run_cli(capsys, ["--fleet", str(fleet), "reset-provider", "codex", "--json"])[0] == 0
    assert _run_cli(capsys, ["--fleet", str(fleet), "set-provider", "claude-p", "0", "--json"])[0] == 0
    code, ra = _run_cli(capsys, ["--fleet", str(fleet), "reset-all", "--json"])
    assert (code, ra["removed"]) == (0, 1)
    assert json.loads(weights.read_text(encoding="utf-8"))["providers"] == {}


def test_active_fleet_resolution_compiled_vs_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """При BRIDGE_COMPILED_FLEET_ENABLED=true и наличии fleet.compiled.json выбирается он."""
    _, _, _, dyn = _env_paths(monkeypatch, tmp_path)
    state_fleet = tmp_path / "state" / "fleet.compiled.json"
    state_fleet.parent.mkdir(parents=True, exist_ok=True)
    state_fleet.write_text(json.dumps(_sample_fleet()), encoding="utf-8")
    dyn.write_text(json.dumps({"BRIDGE_COMPILED_FLEET_ENABLED": True}), encoding="utf-8")
    assert _run_cli(capsys, ["status", "--json"])[1]["active_fleet_path"] == str(state_fleet)

    dyn.write_text(json.dumps({"BRIDGE_COMPILED_FLEET_ENABLED": False}), encoding="utf-8")
    assert _run_cli(capsys, ["status", "--json"])[1]["active_fleet_path"] == str(rw.ROOT / "fleet.json")


@pytest.mark.parametrize("argv", [
    ["set-model", "no-such-model", "codex=10", "--json"],
    ["set-model", "gpt-6.1-sol", "claude-p=10", "--json"],
    ["set-model", "gpt-6.1-sol", "codex=10001", "--json"],
    ["set-model", "gpt-6.1-sol", "codex=-1", "--json"],
    ["set-model", "gpt-6.1-sol", "codex_no_eq", "--json"],
    ["set-provider", "unknown-prov", "50", "--json"],
    ["set-provider", "codex", "abc", "--json"],
])
def test_validation_errors_return_exit_1(
    argv: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ошибки валидации модели, бэкенда, провайдера и веса возвращают код 1."""
    fleet, _, _, _ = _env_paths(monkeypatch, tmp_path)
    code, payload = _run_cli(capsys, ["--fleet", str(fleet), *argv])
    assert code == 1 and payload["ok"] is False


def test_argparse_error_returns_exit_1() -> None:
    """Ошибка разбора CLI-аргументов возвращает код 1, а не 2."""
    with pytest.raises(SystemExit) as exc_info:
        rw.main(["status", "--unknown-flag"])
    assert exc_info.value.code == 1


def test_corrupt_weights_fail_closed_and_repair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Битый файл: status не падает (corrupt=true), мутации дают exit 2, repair создаёт .corrupt."""
    fleet, _, weights, _ = _env_paths(monkeypatch, tmp_path)
    weights.write_text("{broken-json", encoding="utf-8")

    code, st = _run_cli(capsys, ["--fleet", str(fleet), "status", "--json"])
    assert code == 0 and st["corrupt"] is True and st["error"]
    assert _run_cli(capsys, ["--fleet", str(fleet), "set-model", "gpt-6.1-sol", "codex=50", "--json"])[0] == 2
    assert _run_cli(capsys, ["--fleet", str(fleet), "reset-all", "--json"])[0] == 2

    code, rep = _run_cli(capsys, ["--fleet", str(fleet), "repair", "--json"])
    assert code == 0 and Path(rep["backup_path"]).name == "routing_weights.json.corrupt"
    assert Path(rep["backup_path"]).read_text(encoding="utf-8") == "{broken-json"
    assert stat.S_IMODE(weights.stat().st_mode) == 0o600
    assert _run_cli(capsys, ["--fleet", str(fleet), "status", "--json"])[1]["corrupt"] is False


def test_lock_timeout_returns_exit_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Таймаут flock на файле весов возвращает код 3."""
    fleet, _, _, _ = _env_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(RoutingWeightsStore, "mutate", lambda *_a, **_kw: (_ for _ in ()).throw(rw.WeightsLockTimeoutError("busy")))
    code, payload = _run_cli(capsys, ["--fleet", str(fleet), "set-provider", "codex", "40", "--json"])
    assert code == 3 and payload["code"] == 3


def test_doctor_checks_permissions_symlink_stale_and_health(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """doctor проверяет 0600, симлинк, stale model/backend, Python для rebuild и /health."""
    fleet, _, weights, _ = _env_paths(monkeypatch, tmp_path)
    _mock_urlopen(monkeypatch, active=0, ok=True)
    monkeypatch.setenv("BRIDGE_COMPILE_PYTHON", sys.executable)
    monkeypatch.setattr(rw.subprocess, "run", lambda *_a, **_kw: subprocess.CompletedProcess(["py"], 0, "", ""))

    weights.write_text(json.dumps({
        "schema_version": 1, "updated_at": None, "updated_by": "test",
        "providers": {"gone-prov": 10}, "models": {"gone-model": {"codex": 10}, "gpt-6.1-sol": {"gone-be": 20}},
    }), encoding="utf-8")
    os.chmod(weights, 0o644)

    code, doc = _run_cli(capsys, ["--fleet", str(fleet), "doctor", "--json"])
    assert code == 0 and doc["ok"] is False and doc["mode"] == "0644" and doc["mode_ok"] is False
    assert doc["stale_models"] == ["gone-model"] and len(doc["stale_backends"]) == 2 and doc["health"]["reachable"] is True

    os.chmod(weights, 0o600)
    weights.write_text(json.dumps({"schema_version": 1, "updated_at": None, "updated_by": "test", "providers": {}, "models": {}}), encoding="utf-8")
    assert _run_cli(capsys, ["--fleet", str(fleet), "doctor", "--json"])[1]["ok"] is True

    weights.unlink()
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    weights.symlink_to(target)
    doc_sym = _run_cli(capsys, ["--fleet", str(fleet), "doctor", "--json"])[1]
    assert doc_sym["ok"] is False and doc_sym["is_symlink"] is True


def test_rebuild_shadowed_active_turns_and_restart(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Проверяет rebuild: check, RISK-007 (compiled_shadowed=true), active>0 (exit 3), kickstart при active==0."""
    fleet, _, _, dyn = _env_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_COMPILE_PYTHON", "/opt/homebrew/bin/python3")
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "OK\n", "fleet_provider_rejected provider=opencode reason=x\n")

    monkeypatch.setattr(rw.subprocess, "run", _fake_run)
    _mock_urlopen(monkeypatch, active=2)

    code, chk = _run_cli(capsys, ["--fleet", str(fleet), "rebuild", "--json"])
    assert (code, chk["applied"], len(chk["warnings"])) == (0, False, 1)
    assert any("--check" in c for c in calls)

    calls.clear()
    code, sh = _run_cli(capsys, ["--fleet", str(fleet), "rebuild", "--apply", "--json"])
    assert (code, sh["compiled_shadowed"], sh["restarted"]) == (0, True, False)
    assert all(c[0] != "launchctl" for c in calls)

    calls.clear()
    code, df = _run_cli(capsys, ["--fleet", str(fleet), "rebuild", "--apply", "--sync-repo-fleet", "--json"])
    assert (code, df["restart_deferred"], df["restarted"]) == (3, True, False)
    assert any("--sidecar" in c for c in calls)
    assert all(c[0] != "launchctl" for c in calls)

    calls.clear()
    _mock_urlopen(monkeypatch, active=0)
    dyn.write_text(json.dumps({"BRIDGE_COMPILED_FLEET_ENABLED": True}), encoding="utf-8")
    code, ok_rs = _run_cli(capsys, ["--fleet", str(fleet), "rebuild", "--apply", "--json"])
    assert (code, ok_rs["restarted"]) == (0, True)
    assert any(c[:3] == ["launchctl", "kickstart", "-k"] for c in calls)

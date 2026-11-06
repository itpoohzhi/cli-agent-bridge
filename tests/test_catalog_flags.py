"""Флаги каталога и интеграция в server._build_catalog / _load_fleet (DEV-01, Волна 1.6)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

import server
from adapters import ADAPTER_KINDS
from core import catalog_flags
from core.backend_adapter import FleetViolation
from core.catalog_flags import (
    CatalogFlags,
    catalog_flags as read_flags,
    resolve_fleet_path,
    sidecar_allowlist,
)

FLEET_FILE = Path(server.ROOT) / "fleet.json"


def raw_fleet() -> Dict[str, Any]:
    return copy.deepcopy(json.loads(FLEET_FILE.read_text(encoding="utf-8")))


def broken_fleet() -> Dict[str, Any]:
    data = raw_fleet()
    next(m for m in data["models"] if m["id"] == "gpt-6.1-terra")["efforts"] = ["turbo"]
    return data


def test_flags_default_false_and_reader_failures_are_false() -> None:
    assert read_flags(lambda name: False) == CatalogFlags()

    def boom(name: str) -> bool:
        raise RuntimeError(name)

    assert read_flags(boom) == CatalogFlags()
    assert read_flags(
        lambda name: name.endswith("SAFE_CATALOG_ENABLED")
    ) == CatalogFlags(safe_catalog=True)


def test_flags_read_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", "/nonexistent/dynamic.json")
    monkeypatch.setenv("BRIDGE_COMPILED_FLEET_ENABLED", "true")
    flags = read_flags()
    assert (
        flags.compiled_fleet
        and not flags.safe_catalog
        and not flags.provider_constraints
    )


def test_build_catalog_strict_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "catalog_flags", lambda: CatalogFlags())
    with pytest.raises(FleetViolation) as exc:
        server._build_catalog(broken_fleet())
    assert exc.value.reason == "efforts_invalid"


def test_build_catalog_isolates_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "catalog_flags", lambda: CatalogFlags(safe_catalog=True)
    )
    catalog = server._build_catalog(broken_fleet())
    assert catalog["rejected"] == {"gpt-6.1-terra": "efforts_invalid"}
    assert (
        "gpt-6.1-terra" not in catalog["models"] and "gpt-6.1-sol" in catalog["models"]
    )


def test_load_fleet_starts_and_logs_rejected_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps(broken_fleet()), encoding="utf-8")
    monkeypatch.setattr(server, "FLEET_PATH", path)
    monkeypatch.setattr(
        server, "catalog_flags", lambda: CatalogFlags(safe_catalog=True)
    )
    catalog = server._load_fleet()
    assert "gpt-6.1-terra" not in catalog["models"]
    assert (
        "fleet_model_rejected model=gpt-6.1-terra reason=efforts_invalid"
        in capsys.readouterr().err
    )
    assert catalog["path"] == str(path)


def test_load_fleet_still_fatal_without_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps(broken_fleet()), encoding="utf-8")
    monkeypatch.setattr(server, "FLEET_PATH", path)
    monkeypatch.setattr(server, "catalog_flags", lambda: CatalogFlags())
    with pytest.raises(FleetViolation):
        server._load_fleet()


def test_provider_constraints_flag_uses_sidecar_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sidecar = tmp_path / "catalog.lock.json"
    sidecar.write_text(
        json.dumps(
            {
                "providers": {
                    "agy": {
                        "allow_base_url": [
                            {
                                "scheme": "http",
                                "host": "127.0.0.1",
                                "port": 9887,
                                "path_prefix": "/v1",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRIDGE_CATALOG_LOCK", str(sidecar))
    monkeypatch.setattr(
        server, "catalog_flags", lambda: CatalogFlags(provider_constraints=True)
    )
    data = raw_fleet()
    assert server._build_catalog(copy.deepcopy(data))["models"]
    data["backends"]["agy"]["base_url"] = "http://127.0.0.1:9999/v1"
    with pytest.raises(FleetViolation) as exc:
        server._build_catalog(data)
    assert exc.value.reason == "backend_base_url_invalid"


def test_sidecar_allowlist_missing_or_broken_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("BRIDGE_CATALOG_LOCK", raising=False)
    assert sidecar_allowlist() is None
    (tmp_path / "catalog.lock.json").write_text("{not json", encoding="utf-8")
    assert sidecar_allowlist() is None
    (tmp_path / "catalog.lock.json").write_text(
        '{"providers": {"a": {"allow_base_url": [{"scheme": "http"}]}}}',
        encoding="utf-8",
    )
    assert sidecar_allowlist() is None


def write_compiled(state: Path, data: Dict[str, Any]) -> Path:
    state.mkdir(parents=True, exist_ok=True)
    target = state / "fleet.compiled.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    return target


def test_resolve_fleet_path_priorities(tmp_path: Path) -> None:
    default = tmp_path / "default.json"
    env = {"BRIDGE_STATE_DIR": str(tmp_path / "state")}
    compiled = write_compiled(tmp_path / "state", raw_fleet())
    assert (
        resolve_fleet_path(default, ADAPTER_KINDS, env=env, compiled_enabled=False)
        == default
    )
    assert (
        resolve_fleet_path(default, ADAPTER_KINDS, env=env, compiled_enabled=True)
        == compiled
    )
    explicit = dict(env, DROID_DSH_BRIDGE_FLEET=str(tmp_path / "explicit.json"))
    assert (
        resolve_fleet_path(default, ADAPTER_KINDS, env=explicit, compiled_enabled=True)
        == tmp_path / "explicit.json"
    )


def test_resolve_fleet_path_falls_back_on_invalid_or_absent(tmp_path: Path) -> None:
    default = tmp_path / "default.json"
    env = {"BRIDGE_STATE_DIR": str(tmp_path / "state")}
    assert (
        resolve_fleet_path(default, ADAPTER_KINDS, env=env, compiled_enabled=True)
        == default
    )
    write_compiled(tmp_path / "state", broken_fleet())
    assert (
        resolve_fleet_path(default, ADAPTER_KINDS, env=env, compiled_enabled=True)
        == default
    )
    (tmp_path / "state" / "fleet.compiled.json").write_text("garbage", encoding="utf-8")
    assert (
        resolve_fleet_path(default, ADAPTER_KINDS, env=env, compiled_enabled=True)
        == default
    )


def test_state_dir_default_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    assert catalog_flags.state_dir({}).name == "state"
    assert catalog_flags.state_dir({"BRIDGE_STATE_DIR": "/x/y"}) == Path("/x/y")

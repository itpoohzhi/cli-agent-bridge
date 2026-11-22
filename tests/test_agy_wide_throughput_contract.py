"""Контракт высокой параллельности AGY без очередей и локов (128 слотов + FD/breaker/hub plist)."""

from __future__ import annotations

import json
import plistlib
from pathlib import Path
from typing import Any

import yaml

from adapters import ADAPTER_KINDS
from core.fleet_compiler import compile_from_disk

ROOT = Path(__file__).resolve().parents[1]


def test_agy_wide_throughput_128_across_manifests_and_compiled_catalog() -> None:
    """RED-AGY128: providers.d/agy.yaml, fleet.json, catalog.lock.json и компиляция задают agy=128 passthrough."""
    manifest: dict[str, Any] = yaml.safe_load((ROOT / "providers.d/agy.yaml").read_text(encoding="utf-8"))
    assert manifest["kind"] == "passthrough", "RED-AGY128: agy kind must stay passthrough"
    assert manifest["limits"]["max_concurrent"] == 128

    fleet: dict[str, Any] = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    assert fleet["backends"]["agy"]["max_concurrent"] == 128

    lock: dict[str, Any] = json.loads((ROOT / "catalog.lock.json").read_text(encoding="utf-8"))
    assert lock["providers"]["agy"]["max_concurrent"] == 128

    compiled = compile_from_disk(
        ROOT / "providers.d",
        ROOT / "providers.d" / "_fleet.yaml",
        kinds=ADAPTER_KINDS,
        now="2026-11-21T00:00:00+03:00",
    )
    assert compiled.fleet["backends"]["agy"]["max_concurrent"] == 128
    assert compiled.sidecar["providers"]["agy"]["max_concurrent"] == 128


def test_agy_bridge_and_hub_launchd_plist_templates_breaker_and_fd_limits() -> None:
    """F-004: templates dsh-agy-bridge и dsh-hub задают 128/1024, рабочий breaker 8/15, __HOME__ и FD>=4096/8192."""
    agy_plist: dict[str, Any] = plistlib.loads(
        (ROOT / "deploy/launchd/com.user.dsh-agy-bridge.plist").read_bytes()
    )
    agy_env: dict[str, str] = agy_plist["EnvironmentVariables"]
    assert agy_env.get("AGY_BRIDGE_MAX_CONCURRENT") == "128"
    assert int(agy_env.get("AGY_BRIDGE_BREAKER_FAILURES", "0")) in range(3, 17)
    assert int(agy_env.get("AGY_BRIDGE_BREAKER_COOLDOWN_S", "0")) >= 10
    assert agy_env.get("AGY_BRIDGE_QUEUE_TIMEOUT") == "1800"
    assert agy_env.get("HOME") == "__HOME__"
    agy_soft = agy_plist.get("SoftResourceLimits", {}).get("NumberOfFiles", 0)
    agy_hard = agy_plist.get("HardResourceLimits", {}).get("NumberOfFiles", 0)
    assert isinstance(agy_soft, int) and agy_soft >= 4096
    assert isinstance(agy_hard, int) and agy_hard >= 8192

    hub_plist: dict[str, Any] = plistlib.loads(
        (ROOT / "deploy/launchd/com.user.dsh-hub.plist").read_bytes()
    )
    hub_env: dict[str, str] = hub_plist["EnvironmentVariables"]
    assert int(hub_env.get("BRIDGE_MAX_CONCURRENT", "0")) >= 1024
    assert int(hub_env.get("BRIDGE_MAX_HTTP_CONNECTIONS", "0")) >= 1024
    assert hub_env.get("HOME") == "__HOME__"
    hub_soft = hub_plist.get("SoftResourceLimits", {}).get("NumberOfFiles", 0)
    hub_hard = hub_plist.get("HardResourceLimits", {}).get("NumberOfFiles", 0)
    assert isinstance(hub_soft, int) and hub_soft >= 4096
    assert isinstance(hub_hard, int) and hub_hard >= 8192

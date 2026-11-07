from __future__ import annotations

# Тестовые хелперы онбординга droid: стендовые effort каталога и receipt для fake_droid.
#
# Вынесены из `bridge_testlib` (граница размера модуля); `make_receipt` реэкспортируется оттуда.

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def spawn_detached_orphan(seconds: int = 60) -> tuple[int, int]:
    """Запустить `sleep` настоящей сиротой: (pid сироты, pid уже завершившегося родителя).

    Промежуточный родитель стартует ребёнка в новой сессии, печатает его PID и сразу
    выходит, поэтому у сироты мёртвый родитель и проверка живого ppid её не защищает.
    """
    code = (
        "import subprocess,sys\n"
        "p=subprocess.Popen([sys.argv[1],sys.argv[2]],start_new_session=True)\n"
        "print(p.pid,flush=True)\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", code, "sleep", str(seconds)],
        stdout=subprocess.PIPE,
        text=True,
    )
    stdout = parent.stdout
    assert stdout is not None
    try:
        pid = int(stdout.readline())
    finally:
        parent.wait()
        stdout.close()
    return pid, parent.pid


# Уровни effort стенда зафиксированы независимо от боевого каталога (там [low, medium, high]):
# клампы и журнальные тесты моста опираются на high-only и high+max модели.
STAND_EFFORTS = {
    "claude-sonnet-5-5": ["high"],
    "deepseek-v4.1-flash": ["high", "max"],
}


def apply_stand_efforts(model: dict[str, Any]) -> None:
    """Закрепить стендовые efforts модели каталога (если они заданы для неё)."""
    if model["id"] in STAND_EFFORTS:
        model["efforts"] = list(STAND_EFFORTS[model["id"]])
        model["default_effort"] = "high"


def make_receipt(
    image_path: str | Path, digest: str, **override: Any
) -> dict[str, Any]:
    """Receipt schema 2 для fake_droid (протокол по умолчанию fake): тесты ломают по одному компоненту."""
    fake_droid = importlib.import_module("fake_droid")  # tests/ в sys.path

    ids = list(fake_droid.DEFAULT_TOOLS)
    receipt: dict[str, Any] = {
        "schema": server.RECEIPT_SCHEMA,
        "image_path": str(image_path),
        "image_sha256": digest,
        "protocol": {
            "api_version": server.RPC_API_VERSION,
            "protocol_version": fake_droid.PROTOCOL,
        },
        "tools_policy": {
            "policy": server.TOOLS_POLICY,
            "disabled_tool_ids": sorted(ids),
            "digest": server.tools_policy_digest(ids),
        },
        "settings_profile": {
            "profile": dict(server.SETTINGS_PROFILE),
            "digest": server.settings_profile_digest(),
        },
        "probes": {name: "ok" for name in server.RECEIPT_PROBES},
    }
    receipt.update(override)
    return receipt

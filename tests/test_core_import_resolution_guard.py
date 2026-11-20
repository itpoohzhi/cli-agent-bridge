"""W3-G / REQ-009 / RISK-005: `core` разрешается в репозиторий, а не в устаревшую копию.

Мост запускается из `bridges/agy-bridge/server.py` и вставляет корень репозитория в `sys.path[0]`.
Устаревшая копия `core` на `PYTHONPATH` (например, `~/.dsh/bridges/agy-bridge/core`) не должна
затенять новые модули устойчивости; при неполной поставке отказ обязан быть громким и понятным.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NEW_MODULES = (
    "transport_failure_contracts", "transport_failure_classifier", "invisible_retry_policy", "failure_window",
    "hot_session_retention_policy", "tool_call_recovery_policy", "tool_call_completion_tracker",
    "vendor_phrase_sanitizer", "recovery_flags", "turn_resolution_report", "content_delivery_tracker",
    "runtime_build_info", "strict_tool_call_parser", "turn_resilience_facade",
)  # fmt: skip
PROBE = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("bridge_probe", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["bridge_probe"] = module
spec.loader.exec_module(module)
import core
print(core.__file__)
"""


def _run(server: Path, tmp: Path, pythonpath: str = "") -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "AGY_", "PYTHONPATH"))}
    env.update(AGY_BRIDGE_KEY="guard-key", BRIDGE_TELEMETRY_DB_PATH=str(tmp / "t.duckdb"), HOME=str(tmp), PYTHONPATH=pythonpath)
    return subprocess.run([sys.executable, "-c", PROBE, str(server)], capture_output=True, text=True, env=env, cwd=tmp, timeout=60, check=False)  # noqa: S603


def _stale_core(tmp: Path) -> Path:
    stale = tmp / "stale"
    (stale / "core").mkdir(parents=True)
    (stale / "core" / "__init__.py").write_text("STALE = True\n", encoding="utf-8")
    return stale


def test_stale_core_on_pythonpath_does_not_shadow_repo(tmp_path: Path) -> None:
    done = _run(REPO / "bridges" / "agy-bridge" / "server.py", tmp_path, str(_stale_core(tmp_path)))
    assert done.returncode == 0, done.stderr[-800:]
    assert Path(done.stdout.strip().splitlines()[-1]).resolve() == (REPO / "core" / "__init__.py").resolve()


def test_incomplete_deploy_without_facade_fails_loudly(tmp_path: Path) -> None:
    """Поставка с устаревшим `core` (нет фасада) — ModuleNotFoundError с именем модуля, не тихий откат."""
    skip = shutil.ignore_patterns("__pycache__", "workspace", "*.pyc")
    shutil.copytree(REPO / "core", tmp_path / "dsh" / "core", ignore=skip)
    shutil.copytree(REPO / "bridges" / "agy-bridge", tmp_path / "dsh" / "bridges" / "agy-bridge", ignore=skip)
    (tmp_path / "dsh" / "core" / "turn_resilience_facade.py").unlink()
    done = _run(tmp_path / "dsh" / "bridges" / "agy-bridge" / "server.py", tmp_path)
    assert done.returncode != 0 and "turn_resilience_facade" in done.stderr


@pytest.mark.parametrize("name", NEW_MODULES)
def test_new_resilience_modules_exist_and_import_from_repo(name: str) -> None:
    assert (REPO / "core" / f"{name}.py").is_file()
    module = __import__(f"core.{name}", fromlist=["_"])
    assert Path(module.__file__ or "").resolve() == (REPO / "core" / f"{name}.py").resolve()


def test_core_is_a_regular_package_not_a_namespace() -> None:
    assert (REPO / "core" / "__init__.py").is_file()

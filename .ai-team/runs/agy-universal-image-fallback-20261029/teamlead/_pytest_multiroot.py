import gc
import importlib
import sys
import time
from pathlib import Path

_SAVED = {"zen": {}, "root": {}}
_CURRENT = None
_MOD_NAMES = (
    "server",
    "zen_catalog",
    "_fake_cli",
    "_fixtures",
    "_http",
    "rpc_testlib",
    "bridge_testlib",
    "tests",
    "tests._fake_cli",
    "tests._fixtures",
    "tests._http",
    "tests.bridge_testlib",
    "tests.rpc_testlib",
)


def _activate(mode: str, repo_root: Path) -> None:
    global _CURRENT
    zen_dir = str(repo_root / "bridges" / "opencode-zen-bridge")
    zen_tests = str(repo_root / "bridges" / "opencode-zen-bridge" / "tests")
    root_dir = str(repo_root)
    root_tests = str(repo_root / "tests")
    if _CURRENT == mode:
        return
    if _CURRENT is not None:
        for name in list(sys.modules):
            if name in _MOD_NAMES or name.startswith("tests."):
                _SAVED[_CURRENT][name] = sys.modules.pop(name)
    else:
        for name in list(sys.modules):
            if name in _MOD_NAMES or name.startswith("tests."):
                sys.modules.pop(name, None)
    for p in (zen_dir, zen_tests, root_dir, root_tests):
        while p in sys.path:
            sys.path.remove(p)
    if mode == "zen":
        sys.path.insert(0, zen_tests)
        sys.path.insert(0, zen_dir)
        sys.path.insert(2, root_dir)
    else:
        sys.path.insert(0, root_tests)
        sys.path.insert(0, root_dir)
    for name, mod in _SAVED[mode].items():
        sys.modules[name] = mod
    if "server" not in sys.modules:
        importlib.import_module("server")
    _CURRENT = mode
    gc.collect()


def _mode_for_path(fspath) -> str:
    s = str(fspath)
    return "zen" if "opencode-zen-bridge" in s else "root"


def pytest_collectstart(collector):
    p = getattr(collector, "path", None) or getattr(collector, "fspath", None)
    if p is not None and str(p).endswith(".py"):
        _activate(_mode_for_path(p), Path.cwd())


def pytest_collection_modifyitems(session, config, items):
    items.sort(
        key=lambda item: (
            0
            if "test_agy_bridge_resilience.py" in str(item.fspath)
            else (1 if _mode_for_path(item.fspath) == "root" else 2)
        )
    )


def pytest_runtest_setup(item):
    _activate(_mode_for_path(item.fspath), Path.cwd())
    if "test_tc93" in item.name:
        gc.collect()


def pytest_runtest_teardown(item):
    s = str(item.fspath)
    if "test_rpc_" in s:
        time.sleep(0.15)
        srv = sys.modules.get("server")
        if srv is not None and hasattr(srv, "shutdown_all"):
            try:
                srv.shutdown_all()
            except Exception:
                pass
            time.sleep(0.05)

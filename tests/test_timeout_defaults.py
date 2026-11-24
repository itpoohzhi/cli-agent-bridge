"""Contract tests for cli-agent-bridge timeout defaults (wave WB4).

Pure source/AST checks plus lightweight unit checks of the root server
Handler effective-timeout helpers. No network calls, no real sleeps and
no HTTP server is ever started (T-ISO compliant).
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIDGE_PATHS = {
    "muse": ROOT / "bridges" / "muse-bridge" / "server.py",
    "agy": ROOT / "bridges" / "agy-bridge" / "server.py",
    "claude-p": ROOT / "bridges" / "claude-p-bridge" / "server.py",
}


def _src(path: Path) -> str:
    assert path.is_file(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


def _assign_number(src: str, name: str) -> float:
    """Numeric value of a `name = <number>` (possibly annotated) line."""
    pattern = (
        r"^[ \t]*" + re.escape(name) + r"\s*(?::[^=\n]+)?=\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:#.*)?$"
    )
    for line in src.splitlines():
        match = re.match(pattern, line)
        if match:
            return float(match.group(1))
    raise AssertionError(f"numeric assignment for {name!r} not found")


def _call_args(src: str, name: str) -> list:
    """Positional arguments of the module-level `name = <call>(...)`."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            assert isinstance(node.value, ast.Call), f"{name!r} is not a call"
            return node.value.args
    raise AssertionError(f"assignment {name!r} not found")


def _chain_float_call(src: str, env_name: str) -> ast.Call:
    """The `_chain_float(...)` call (anywhere in the module) whose first
    positional argument is a tuple containing the constant `env_name`."""
    for node in ast.walk(ast.parse(src)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_chain_float"
            and node.args
            and isinstance(node.args[0], ast.Tuple)
            and any(
                isinstance(el, ast.Constant) and el.value == env_name
                for el in node.args[0].elts
            )
        ):
            return node
    raise AssertionError(f"_chain_float call for {env_name!r} not found")


class _Headers(dict):
    """Minimal case-insensitive header mapping (no HTTP machinery)."""

    def get(self, key, default=None):  # noqa: A003
        lowered = str(key).lower()
        for name, value in self.items():
            if str(name).lower() == lowered:
                return value
        return default


def _load_server(name: str, path: Path):
    """Import a server module from an explicit file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def root_server():
    return _load_server("bridge_root_server", ROOT / "server.py")


@pytest.fixture(scope="module")
def muse_bridge():
    return _load_server("muse_bridge_wb4_under_test", BRIDGE_PATHS["muse"])


def _handler(server_module, headers):
    """Handler stub exposing effective-timeout helpers (no server needed)."""
    handler = server_module.Handler.__new__(server_module.Handler)
    handler.headers = _Headers(headers)
    handler._is_subagent_request = lambda: True
    return handler

# --- 1. root server (ROOT/server.py): timeout defaults ---------------------


def test_root_server_source_defaults(root_server):
    assert root_server.TIMEOUT_S == 3600.0
    assert root_server.IDLE_TIMEOUT_S == 600.0
    assert root_server.SUBAGENT_WATCHDOG_CAP_S == 1800.0
    assert root_server.Handler.timeout == 3600
    assert root_server.Handler.timeout >= root_server.TIMEOUT_S

# --- 2. muse bridge (bridges/muse-bridge/server.py): defaults --------------


def test_muse_bridge_source_defaults(muse_bridge):
    src = _src(BRIDGE_PATHS["muse"])
    assert "SUBAGENT_WATCHDOG_CAP_S" not in src
    assert muse_bridge.TIMEOUT_S == 3600.0
    assert muse_bridge.IDLE_TIMEOUT_S == 600.0
    assert muse_bridge.Handler.timeout == 1800

# --- 3. root server: Handler effective-timeout helpers ---------------------


def test_effective_defaults_without_headers(root_server):
    handler = _handler(root_server, {})
    assert handler._effective_safety_cap_s() == 1800.0
    assert handler._effective_idle_timeout_s() == 600.0


@pytest.mark.parametrize("cap_header", ["900", "1200", "3600"])
def test_effective_cap_from_watchdog_header(root_server, cap_header):
    handler = _handler(root_server, {"X-Watchdog-Cap-Seconds": cap_header})
    assert handler._effective_safety_cap_s() == float(cap_header)


def test_effective_cap_clamped_by_server_timeout(root_server):
    handler = _handler(root_server, {"X-Watchdog-Cap-Seconds": "99999"})
    assert handler._effective_safety_cap_s() == root_server.TIMEOUT_S


def test_idle_header_does_not_change_cap(root_server):
    handler = _handler(root_server, {"X-Timeout-Seconds": "720"})
    assert handler._effective_idle_timeout_s() == 720.0
    assert handler._effective_safety_cap_s() == 1800.0

# --- 4. core/watchdog.py ----------------------------------------------------


def test_watchdog_finish_reserve_s():
    try:
        from core.watchdog import WatchdogConfig
    except Exception:
        src = _src(ROOT / "core" / "watchdog.py")
        match = re.search(r"finish_reserve_s[^=\n]*=\s*([0-9.]+)", src)
        assert match and float(match.group(1)) == 35.0
        return
    assert WatchdogConfig().finish_reserve_s == 35.0

# --- 5. adapters/passthrough_adapter.py ------------------------------------


def test_passthrough_adapter_defaults():
    try:
        import adapters.passthrough_adapter as adapter
    except Exception:
        src = _src(ROOT / "adapters" / "passthrough_adapter.py")
        assert _assign_number(src, "DEFAULT_IDLE_TIMEOUT_S") == 600.0
        assert _assign_number(src, "DEFAULT_TOTAL_TIMEOUT_S") == 1800.0
        return
    assert adapter.DEFAULT_IDLE_TIMEOUT_S == 600.0
    assert adapter.DEFAULT_TOTAL_TIMEOUT_S == 1800.0

# --- 6. turn deadlines and stdio pool config -------------------------------


def test_turn_deadline_defaults():
    names = (
        "DEFAULT_FIRST_PROGRESS_TIMEOUT_S",
        "DEFAULT_TURN_IDLE_TIMEOUT_S",
        "DEFAULT_SAFETY_CAP_S",
    )
    try:
        from core.stdio_resident import turn_deadlines as deadlines
        values = tuple(getattr(deadlines, name) for name in names)
    except Exception:
        src = _src(ROOT / "core" / "stdio_resident" / "turn_deadlines.py")
        values = tuple(_assign_number(src, name) for name in names)
    assert values == (720.0, 600.0, 1800.0)


def _stdio_pool_config_cls():
    for module_name in ("core.stdio_resident.config", "core.config", "config"):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        cls = getattr(module, "StdioPoolConfig", None)
        if cls is not None:
            return cls
    return None


def _stdio_pool_config_source() -> str:
    candidates = [ROOT / "core" / "config.py", ROOT / "config.py"]
    candidates += sorted((ROOT / "core").rglob("*.py"))
    for path in candidates:
        if path.is_file():
            source = _src(path)
            if "class StdioPoolConfig" in source:
                return source
    raise AssertionError("StdioPoolConfig source not found")


def test_stdio_pool_config_defaults():
    cls = _stdio_pool_config_cls()
    if cls is not None:
        config = cls()
        assert config.turn_idle_timeout_s == 600.0
        assert config.turn_total_timeout_s == 1800.0
        return
    source = _stdio_pool_config_source()
    assert _assign_number(source, "turn_idle_timeout_s") == 600.0
    assert _assign_number(source, "turn_total_timeout_s") == 1800.0

# --- 7. standalone bridges: source-level defaults --------------------------


def test_agy_bridge_source_defaults():
    src = _src(BRIDGE_PATHS["agy"])
    first = _chain_float_call(src, "AGY_BRIDGE_FIRST_TOKEN_TIMEOUT_S")
    assert isinstance(first.args[1], ast.Constant)
    assert first.args[1].value == 720.0
    base = _chain_float_call(src, "AGY_BRIDGE_BASE_IDLE_TIMEOUT_S")
    assert isinstance(base.args[1], ast.Call)
    assert isinstance(base.args[1].args[0], ast.Constant)
    assert base.args[1].args[0].value == 600.0
    assert re.search(
        r'protocol_version\s*=\s*"HTTP/1\.1"\s*;\s*timeout\s*=\s*1800\b', src
    )


def test_claude_p_bridge_source_defaults():
    src = _src(BRIDGE_PATHS["claude-p"])
    idle_args = _call_args(src, "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S")
    assert len(idle_args) >= 3
    assert isinstance(idle_args[2], ast.Constant) and idle_args[2].value == 600.0
    http_env = _call_args(src, "HTTP_TIMEOUT_S")[0]
    assert isinstance(http_env, ast.Call) and len(http_env.args) >= 2
    default = http_env.args[1]
    assert isinstance(default, ast.Constant) and default.value == "1800"

"""Contract tests for Claude Zero-Canon in cli-agent-bridge (RED in W0-C1, <=250 LOC)."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "zero-canon-allowlist.json"
CORE_PATH = ROOT / "core" / "claude_zero_canon.py"
SERVER_PATH = ROOT / "bridges" / "claude-p-bridge" / "server.py"
FORBIDDEN_IMPORTS = frozenset({
    "os", "pathlib", "subprocess", "shutil", "tempfile", "pwd", "socket",
    "http", "urllib", "sys", "signal", "atexit", "threading", "importlib",
})
CC_NODES = (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.IfExp)
CA_FILES = {
    "aeza-8788-ca.pem": b"---CA-1---\n", "bundle-with-aeza.pem": b"---BUNDLE-2---\n",
    "policy-limits.json": b'{"limit":1}\n', "policy-limits.json.signature.json": b'{"sig":"ok"}\n',
}

def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

def _load_mod(path: Path, name: str, mp: pytest.MonkeyPatch | None = None):
    assert path.is_file(), f"Missing module: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mp.setitem(sys.modules, name, mod) if mp else sys.modules.__setitem__(name, mod)
    spec.loader.exec_module(mod)
    return mod

def _load_core():
    return _load_mod(CORE_PATH, "core.claude_zero_canon")

def _assert_server_ast() -> ast.Module:
    assert SERVER_PATH.is_file(), f"Missing server module: {SERVER_PATH}"
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    ok = any(
        (isinstance(n, ast.Import) and any("claude_zero_canon" in a.name for a in n.names))
        or (isinstance(n, ast.ImportFrom) and n.module and (
            "claude_zero_canon" in n.module or any(a.name == "claude_zero_canon" for a in n.names)
        )) for n in ast.walk(tree)
    )
    assert ok, "server.py must import core.claude_zero_canon"
    return tree

def _load_server(mp: pytest.MonkeyPatch, real_home: Path, sandbox_home: Path):
    mp.setenv("HOME", str(real_home))
    mp.setenv("CLAUDE_CONFIG_DIR", str(sandbox_home / ".claude"))
    mp.setattr(Path, "home", classmethod(lambda cls: real_home))
    mp.syspath_prepend(str(ROOT))
    mp.syspath_prepend(str(SERVER_PATH.parent))
    mod = _load_mod(SERVER_PATH, "claude_p_bridge_server_zc_test", mp)
    for attr in ("CLAUDE_HOME", "CLAUDE_BRIDGE_HOME", "ISOLATED_CLAUDE_HOME"):
        if hasattr(mod, attr):
            mp.setattr(mod, attr, sandbox_home if isinstance(getattr(mod, attr), Path) else str(sandbox_home))
    return mod

def _invoke_prepare(srv, sandbox_home: Path, real_home: Path) -> Path:
    fn = getattr(srv, "_prepare_claude_home", None)
    assert callable(fn), "Missing _prepare_claude_home in server.py"
    p = list(inspect.signature(fn).parameters)
    if {"claude_home", "real_home"} <= set(p):
        res = fn(claude_home=sandbox_home, real_home=real_home)
    elif p == ["real_home"]:
        res = fn(real_home=real_home)
    else:
        res = fn(*((sandbox_home, real_home)[:len(p)]))
    return Path(res) if res is not None else sandbox_home

def _setup_homes(tmp_path: Path, settings: dict) -> tuple[Path, Path, Path]:
    real_home, sandbox_home = tmp_path / "real", tmp_path / "sandbox"
    (real_home / ".claude").mkdir(parents=True)
    sb_cl = sandbox_home / ".claude"
    sb_cl.mkdir(parents=True)
    (real_home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return real_home, sandbox_home, sb_cl

def _cc(fn: ast.AST) -> int:
    return 1 + sum(
        1 if isinstance(n, CC_NODES) else (len(n.values) - 1 if isinstance(n, ast.BoolOp)
        else (len(n.ifs) if isinstance(n, ast.comprehension) else 0)) for n in ast.walk(fn)
    )

def _has_pair(argv: list[str], flag: str, val: str) -> bool:
    return any(argv[i] == flag and argv[i + 1] == val for i in range(len(argv) - 1))

def _find_func(tree: ast.Module, name: str) -> ast.FunctionDef:
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"Function {name!r} not found in {SERVER_PATH}"
    return fn

def _has_call(node: ast.AST, target: str) -> bool:
    return any(
        isinstance(s, ast.Call) and ((isinstance(s.func, ast.Name) and s.func.id == target)
        or (isinstance(s.func, ast.Attribute) and s.func.attr == target)) for s in ast.walk(node)
    )

def test_core_fixture_parity() -> None:
    golden, core = _load_fixture(), _load_core()
    prov = {"seat_zero_canon.py", "seat_zero_profile.py", "DEC-002", "DEC-004"}
    assert golden["schema_version"] == "1.0"
    assert golden["claude"]["provenance"] and set(golden["claude"]["provenance"]) <= prov
    assert golden["forbidden_flags"]["provenance"] and set(golden["forbidden_flags"]["provenance"]) <= prov
    assert set(core.CLAUDE_SETTINGS_ALLOWLIST) == set(golden["claude"]["settings_allowlist"])
    assert set(core.CLAUDE_STATE_ALLOWLIST) == set(golden["claude"]["state_allowlist"])
    assert dict(core.CLAUDE_ENV_OVERLAY) == golden["claude"]["env_overlay"]
    assert set(core.CLAUDE_FORBIDDEN_FLAGS) == set(golden["forbidden_flags"]["claude"])

def test_core_filter_settings_and_state() -> None:
    core = _load_core()
    raw = {
        "env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:9999"}, "apiKeyHelper": "/bin/key",
        "forceLoginMethod": "claudeai", "forceLoginOrgUUID": "org-1",
        "hooks": {"PreToolUse": ["x"]}, "mcpServers": {"evil": {"command": "sh"}},
        "permissions": {"allow": ["Bash"]}, "enabledPlugins": {"p": True},
    }
    filtered = core.filter_claude_settings(raw)
    assert set(filtered) == {"env", "apiKeyHelper", "forceLoginMethod", "forceLoginOrgUUID"}
    filtered["env"]["ANTHROPIC_BASE_URL"] = "mutated"
    assert raw["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:9999"
    state = {
        "oauthAccount": {"id": "1"}, "userID": "u1", "hasCompletedOnboarding": True,
        "lastOnboardingVersion": "1.0", "customApiKeyResponses": {}, "projects": {"/tmp": {}}, "mcpServers": {"m": {}},
    }
    assert set(core.filter_claude_state(state)) == set(core.CLAUDE_STATE_ALLOWLIST)

def test_core_build_flags_and_env() -> None:
    core = _load_core()
    txt = list(core.build_claude_zero_canon_flags(has_images=False))
    img = list(core.build_claude_zero_canon_flags(has_images=True))
    for flags in (txt, img):
        assert _has_pair(flags, "--setting-sources", "user")
        assert {"--disable-slash-commands", "--no-session-persistence", "--strict-mcp-config"} <= set(flags)
    assert _has_pair(txt, "--tools", "") and _has_pair(img, "--tools", "Read")
    env = core.build_claude_zero_canon_env({"PATH": "/usr/bin", "CLAUDE_CONFIG_DIR": "/stale"}, "/tmp/zc-claude/")
    assert env["HOME"] == "/tmp/zc-claude" and env["CLAUDE_CONFIG_DIR"] == "/tmp/zc-claude/.claude"
    assert env["PATH"] == "/usr/bin"

def test_core_ast_imports() -> None:
    assert CORE_PATH.is_file(), f"Missing {CORE_PATH}"
    for n in ast.walk(ast.parse(CORE_PATH.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            assert all(a.name.split(".")[0] not in FORBIDDEN_IMPORTS for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            assert n.module.split(".")[0] not in FORBIDDEN_IMPORTS

def test_core_ast_limits() -> None:
    assert CORE_PATH.is_file(), f"Missing {CORE_PATH}"
    src = CORE_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 250
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert n.end_lineno is not None and (n.end_lineno - n.lineno + 1) <= 40, n.name
            args = [a for a in (*n.args.posonlyargs, *n.args.args, *n.args.kwonlyargs) if a.arg not in ("self", "cls")]
            assert len(args) <= 5 and _cc(n) <= 10, n.name

def test_core_review_profile_value_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    golden = _load_fixture()
    assert golden["review_profile_value"] == "Zero-Canon"
    monkeypatch.syspath_prepend(str(ROOT))
    param_adapter = importlib.import_module("core.param_adapter")
    assert golden["review_profile_value"].lower() == param_adapter.REVIEW_PROFILE_HEADER_VALUE
    assert "Zero-Canon".lower() == param_adapter.REVIEW_PROFILE_HEADER_VALUE

def test_server_uses_claude_zero_canon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = _assert_server_ast()
    assert _has_call(_find_func(tree, "_build_claude_cmd"), "build_claude_zero_canon_flags")
    assert _has_call(_find_func(tree, "_prepare_claude_home"), "filter_claude_settings")
    srv = _load_server(monkeypatch, tmp_path / "real", tmp_path / "sandbox")
    assert callable(getattr(srv, "_prepare_claude_home", None)) and callable(getattr(srv, "_build_claude_cmd", None))

def test_server_explicit_claude_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = _assert_server_ast()
    has_key = any(isinstance(n, ast.Constant) and n.value == "CLAUDE_CONFIG_DIR" for n in ast.walk(tree))
    assert has_key or _has_call(tree, "build_claude_zero_canon_env")
    _load_server(monkeypatch, tmp_path / "real", tmp_path / "sandbox")
    env = _load_core().build_claude_zero_canon_env({"CLAUDE_CONFIG_DIR": "/wrong"}, str(tmp_path / "sandbox"))
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "sandbox" / ".claude")

def test_server_preserves_ca_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _assert_server_ast()
    real_home, sandbox_home, sb_cl = _setup_homes(
        tmp_path, {"env": {"A": "1"}, "apiKeyHelper": "/bin/k", "hooks": {"PreToolUse": []}, "mcpServers": {"b": {}}},
    )
    for name, body in CA_FILES.items():
        (sb_cl / name).write_bytes(body)
    _invoke_prepare(_load_server(monkeypatch, real_home, sandbox_home), sandbox_home, real_home)
    for name, body in CA_FILES.items():
        assert (sb_cl / name).read_bytes() == body
    assert json.loads((sb_cl / "settings.json").read_text(encoding="utf-8")) == {"env": {"A": "1"}, "apiKeyHelper": "/bin/k"}

def test_server_settings_atomic_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _assert_server_ast()
    real_home, sandbox_home, sb_cl = _setup_homes(
        tmp_path, {"env": {"A": "1"}, "forceLoginMethod": "claudeai", "hooks": {"x": 1}},
    )
    mk_dirs, replaces = [], []
    orig_mk, orig_rep = tempfile.mkstemp, os.replace
    def spy_mk(*args, **kwargs):
        d = kwargs.get("dir", args[2] if len(args) >= 3 else None)
        mk_dirs.append(Path(d) if d is not None else None)
        return orig_mk(*args, **kwargs)
    def spy_rep(src, dst):
        replaces.append((Path(src), Path(dst)))
        return orig_rep(src, dst)
    monkeypatch.setattr(tempfile, "mkstemp", spy_mk)
    monkeypatch.setattr(os, "replace", spy_rep)
    srv = _load_server(monkeypatch, real_home, sandbox_home)
    mk_dirs[:], replaces[:] = [], []
    _invoke_prepare(srv, sandbox_home, real_home)
    sp = sb_cl / "settings.json"
    assert sp.is_file() and (sp.stat().st_mode & 0o777) == 0o600
    assert any(d is not None and d.resolve() == sb_cl.resolve() for d in mk_dirs)
    assert any(dst.resolve() == sp.resolve() and src.parent.resolve() == sb_cl.resolve() for src, dst in replaces)
    replaces.clear()
    _invoke_prepare(srv, sandbox_home, real_home)
    assert not any(dst.resolve() == sp.resolve() for _, dst in replaces)

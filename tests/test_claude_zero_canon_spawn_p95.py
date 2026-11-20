"""Hot-Path gate: p95 спавна claude -p (Zero-Canon) против базы 231b9be, stub-CLI в песочнице."""
from __future__ import annotations

import contextlib
import http.client
import importlib.util
import json
import math
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "bridges" / "claude-p-bridge" / "server.py"
BASE_SHA = "231b9beac6044b134cd207813a1f25143b7ab864"
KEY = "test-key"
HDRS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
SETTINGS = {"env": {"A": "1"}, "forceLoginMethod": "claudeai", "hooks": {"x": 1}}
STUB = """#!/bin/sh
if [ -n "$ZC_PROBE_FILE" ]; then
  { echo "CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR"; echo "HOME=$HOME"; printf 'ARG=%s\\n' "$@"; } >> "$ZC_PROBE_FILE"
fi
cat >/dev/null
echo '{"type":"stream_event","event":{"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}}'
echo '{"type":"result","subtype":"success","is_error":false,"result":"ok","usage":{"input_tokens":1,"output_tokens":1}}'
"""


def _base_source() -> bytes:
    """Базовая реализация строго из git (в тех же условиях, что и new)."""
    return subprocess.run(
        ["git", "show", f"{BASE_SHA}:bridges/claude-p-bridge/server.py"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout


def _load(mp: pytest.MonkeyPatch, name: str, src: Path, paths: tuple[Path, Path, Path]):
    """Загрузить server.py под уникальным именем и направить его в песочницу."""
    ws, mcp, stub = paths
    spec = importlib.util.spec_from_file_location(name, src)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mp.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    ws.mkdir(parents=True, exist_ok=True)
    mod.AUTH_KEY, mod.MAX_CONCURRENT = KEY, 64
    mod.WORKSPACE, mod.MCP_CONFIG, mod.CLAUDE_BIN = ws, mcp, str(stub)
    return mod


def _snap(home: Path) -> list:
    """Снимок дерева (путь, содержимое) для проверки, что реальный HOME не тронут."""
    return sorted((str(p.relative_to(home)), p.read_bytes() if p.is_file() else b"") for p in home.rglob("*"))


@pytest.fixture
def sb(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    mp = monkeypatch
    base_src = tmp_path / "base" / "server.py"
    base_src.parent.mkdir()
    base_src.write_bytes(_base_source())
    for var in PROXY_VARS:
        mp.delenv(var, raising=False)
    mp.setenv("NO_PROXY", "127.0.0.1")
    mp.setenv("no_proxy", "127.0.0.1")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
    mp.setenv("HOME", str(home))
    mp.setattr(Path, "home", classmethod(lambda cls: home))
    mp.setenv("CLAUDE_P_BRIDGE_KEY", KEY)
    mp.delenv("CLAUDE_CONFIG_DIR", raising=False)
    stub = tmp_path / "claude-stub.sh"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    mcp = tmp_path / "mcp.json"
    mcp.write_text('{"mcpServers":{}}', encoding="utf-8")
    mp.syspath_prepend(str(ROOT))
    mp.syspath_prepend(str(SERVER_PATH.parent))
    mods = {
        k: _load(mp, f"zc_p95_{k}", src, (tmp_path / f"ws_{k}", mcp, stub))
        for k, src in (("base", base_src), ("new", SERVER_PATH))
    }
    return SimpleNamespace(home=home, tmp=tmp_path, **mods)


@contextlib.contextmanager
def _serve(mod):
    srv = mod.Server(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()
        srv.server_close()


def _post(port: int, barrier: threading.Barrier | None = None) -> tuple[int, float]:
    body = json.dumps({"messages": [{"role": "user", "content": "ping"}]})
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    try:
        if barrier is not None:
            barrier.wait(60)
        t0 = time.perf_counter()
        conn.request("POST", "/v1/chat/completions", body, HDRS)
        resp = conn.getresponse()
        resp.read()
        return resp.status, (time.perf_counter() - t0) * 1000.0
    finally:
        conn.close()


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _round(port: int, n: int) -> float:
    """Один раунд: n одновременных POST (барьер), возвращает p95 в мс."""
    barrier = threading.Barrier(n)
    with ThreadPoolExecutor(max_workers=n) as ex:
        out = list(ex.map(lambda _: _post(port, barrier), range(n)))
    assert all(status == 200 for status, _ in out), [status for status, _ in out]
    return _p95([ms for _, ms in out])


def test_spawn_p95_vs_base_and_scaling(sb: SimpleNamespace) -> None:
    before = _snap(sb.home)
    res: dict[str, list[float]] = {"base": [], "new": []}
    with _serve(sb.base) as p_base, _serve(sb.new) as p_new:
        ports = {"base": p_base, "new": p_new}
        for i in range(6):  # раунд 0 — прогрев, отбрасывается
            order = ("base", "new") if i % 2 == 0 else ("new", "base")
            for key in order:
                value = _round(ports[key], 32)
                if i > 0:
                    res[key].append(value)
        p95_n8 = statistics.median(_round(p_new, 8) for _ in range(5))
    m_base, m_new = statistics.median(res["base"]), statistics.median(res["new"])
    limit = max(10.0, 0.2 * m_base)
    assert m_new - m_base <= limit, f"p95 new={m_new:.1f}ms base={m_base:.1f}ms limit={limit:.1f}ms {res}"
    ratio = m_new / p95_n8
    assert ratio <= 2.0, f"p95(N=32)/p95(N=8)={ratio:.2f} (n32={m_new:.1f}ms n8={p95_n8:.1f}ms)"
    assert _snap(sb.home) == before, "реальный HOME изменён"


def test_stub_env_has_config_dir_and_flags(sb: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    probe = sb.tmp / "probe.txt"
    monkeypatch.setenv("ZC_PROBE_FILE", str(probe))
    before = _snap(sb.home)
    with _serve(sb.new) as port:
        status, _ = _post(port)
    assert status == 200
    lines = probe.read_text(encoding="utf-8").splitlines()
    env = dict(ln.split("=", 1) for ln in lines if not ln.startswith("ARG="))
    argv = [ln[4:] for ln in lines if ln.startswith("ARG=")]
    claude_home = sb.new.WORKSPACE / "runtime" / "claude-home"
    assert Path(env["CLAUDE_CONFIG_DIR"]).resolve() == (claude_home / ".claude").resolve()
    assert Path(env["HOME"]).resolve() == claude_home.resolve()
    assert Path(env["HOME"]).resolve() != sb.home.resolve()
    for flag in ("--disable-slash-commands", "--no-session-persistence", "--strict-mcp-config"):
        assert flag in argv, (flag, argv)
    assert _snap(sb.home) == before, "реальный HOME изменён"


def test_settings_concurrent_writes_never_partial(sb: SimpleNamespace) -> None:
    mod = sb.new
    root = sb.tmp / "atomic"
    dest = root / ".claude" / "settings.json"
    dest.parent.mkdir(parents=True)
    bodies = [
        json.dumps({"env": {f"K{j}": str(i) * 64 for j in range(400)}, "i": i}).encode("utf-8")
        for i in range(4)
    ]
    mod._write_atomic(dest, bodies[0])
    stop, errors = threading.Event(), []

    def reader() -> None:
        while not stop.is_set():
            try:
                json.loads(dest.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:  # частичный файл / файл исчез
                errors.append(repr(exc))

    def writer(i: int) -> None:
        for n in range(40):
            mod._write_atomic(dest, bodies[(i + n) % 4])
            mod._prepare_claude_home(claude_home=root, real_home=sb.home)

    readers = [threading.Thread(target=reader, daemon=True) for _ in range(4)]
    for t in readers:
        t.start()
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for fut in [ex.submit(writer, i) for i in range(8)]:
                fut.result(timeout=120)
    finally:
        stop.set()
        for t in readers:
            t.join(timeout=10)
    assert not errors, errors[:3]
    assert (dest.stat().st_mode & 0o777) == 0o600
    assert not list(dest.parent.glob(".tmp_*")), "остались временные файлы"
    assert isinstance(json.loads(dest.read_text(encoding="utf-8")), dict)

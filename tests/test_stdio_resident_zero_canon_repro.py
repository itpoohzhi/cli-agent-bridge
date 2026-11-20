"""Репро 180-с бага stdio_resident (claude/codex) и Zero-Canon-изоляция; всё в tmp_path."""

from __future__ import annotations

import json
import sys
import time
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from adapters.stdio_drivers import build_affinity_key, infer_protocol
from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver
from core.stdio_resident.codex_driver import CodexAppServerDriver
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import ResidentProcessHandle
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.protocol_driver import DecodedChunk, StreamJsonDriver
from core.stdio_resident.session_manager import StdioSessionManager
from core.stdio_resident.turn_error_sse import build_turn_error
from core.stdio_resident.types import SlotAffinityKey

ROOT = Path(__file__).resolve().parents[1]
FAKE_PROCESS = ROOT / "tests" / "stdio_fake_agent.py"
RATE_LIMIT_LINE = {"type": "result", "is_error": True, "api_error_status": 429, "result": "rate limit hit"}

AGENT = '''
import json, os, sys, time
mode = sys.argv[1]
sys.stdin.readline()
if mode == "rate_limit":
    print(json.dumps({"type": "result", "is_error": True, "api_error_status": 429, "result": "rate limit hit"}), flush=True)
    time.sleep(60)
elif mode == "silent":
    time.sleep(60)
elif mode == "eof":
    sys.exit(0)
else:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR", "")
    settings = open(cfg + "/settings.json").read() if os.path.exists(cfg + "/settings.json") else ""
    info = {"home": os.environ.get("HOME"), "cfg": cfg, "settings": settings, "argv": sys.argv[1:]}
    print(json.dumps({"type": "result", "result": json.dumps(info)}), flush=True)
    time.sleep(60)
'''


def _config(idle: float = 180.0) -> StdioPoolConfig:
    return StdioPoolConfig(
        max_slots=4, idle_timeout_s=30.0, ttl_s=30.0, max_rss_bytes=128 * 1024 * 1024,
        lease_wait_s=0.5, cancel_grace_s=0.2, shutdown_timeout_s=0.5, enabled=True,
        turn_idle_timeout_s=idle, handshake_timeout_s=5.0,
    )


def _key(chat: str, profile: str = "standard", model: str = "sonnet") -> SlotAffinityKey:
    return SlotAffinityKey("owner", chat, "claude-p", model, "high", str(ROOT), profile)


@pytest.fixture
def agent(tmp_path: Path) -> Path:
    path = tmp_path / "fake_agent.py"
    path.write_text(AGENT, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _tmp_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    yield


def _manager(driver: object, idle: float = 180.0) -> tuple[StdioSessionManager, ResidentProcessPool]:
    pool = ResidentProcessPool(_config(idle))
    return StdioSessionManager(pool, driver, _config(idle)), pool  # type: ignore[arg-type]


def test_infer_protocol_recognizes_claude_and_codex() -> None:
    assert infer_protocol("claude-p", {}, {}) == "claude-stream-json"
    assert infer_protocol("claude", {}, {}) == "claude-stream-json"
    assert infer_protocol("codex", {}, {}) == "codex-app-server"
    assert infer_protocol("x", {"wrapper": "/opt/bin/claude-p-cli.sh"}, {}) == "claude-stream-json"
    assert infer_protocol("x", {"wrapper_path": "/opt/bin/codex"}, {}) == "codex-app-server"
    # Регрессия: прежние выводы и явная опция не изменились.
    assert infer_protocol("muse", {}, {}) == "msp-v1"
    assert infer_protocol("opencode", {}, {}) == "opencode-acp"
    assert infer_protocol("claude-p", {}, {"protocol": "acp"}) == "acp"
    assert infer_protocol("other", {}, {}) == "stream-json"


def test_slot_affinity_key_review_profile_is_backward_compatible() -> None:
    legacy = SlotAffinityKey("o", "c", "b", "m", "e", "/w")
    assert legacy.review_profile == "standard"
    assert legacy == SlotAffinityKey("o", "c", "b", "m", "e", "/w", "standard")
    assert legacy != SlotAffinityKey("o", "c", "b", "m", "e", "/w", "zero-canon")
    built = build_affinity_key("o", "c", "b", "m", "e", "/w", review_profile="Zero-Canon")
    assert built.review_profile == "zero-canon"
    assert StdioSessionManager._session_key(legacy) != StdioSessionManager._session_key(built)


def test_read_line_outcome_separates_timeout_from_eof() -> None:
    handle = ResidentProcessHandle.spawn([sys.executable, "-c", "import time; time.sleep(30)"], cwd=str(ROOT))
    try:
        assert handle.read_line_outcome(timeout_s=0.1) == ("timeout", None)
        assert handle.read_line(timeout_s=0.05) is None  # обратная совместимость
        handle.proc.kill()
        deadline = time.monotonic() + 5.0
        kind = "timeout"
        while kind == "timeout" and time.monotonic() < deadline:
            kind, line = handle.read_line_outcome(timeout_s=0.5)
        assert (kind, line) == ("eof", None)
    finally:
        handle.terminate_gracefully(grace_s=0.2)
    echo = ResidentProcessHandle.spawn([sys.executable, str(FAKE_PROCESS)], cwd=str(ROOT))
    try:
        echo.write(b"hello\n")
        kind, tagged = echo.read_line_outcome(timeout_s=3.0)
        assert kind == "line" and tagged is not None and tagged.line
    finally:
        echo.terminate_gracefully(grace_s=0.5)


def test_claude_driver_decodes_error_and_429_retry_fast() -> None:
    driver = ClaudeStreamJsonDriver()
    final = driver.decode_line(json.dumps(RATE_LIMIT_LINE))
    assert final is not None and final.is_terminal and final.text == "rate limit hit"
    assert final.error is not None and "429" in final.error and final.raw["is_error"] is True
    retry = driver.decode_line('{"type":"system","subtype":"api_retry","error_status":429,"error":"rate_limit"}')
    assert retry is not None and retry.error is not None and "429" in retry.error
    benign = driver.decode_line('{"type":"system","subtype":"api_retry","error_status":529}')
    assert benign is not None and benign.error is None
    ok = driver.decode_line('{"type":"result","result":"done","is_error":false}')
    assert ok is not None and ok.error is None and DecodedChunk().error is None


def test_rate_limit_fails_fast_without_waiting_idle_timeout(agent: Path) -> None:
    manager, pool = _manager(ClaudeStreamJsonDriver(), idle=180.0)
    started = time.monotonic()
    try:
        with pytest.raises(RuntimeError, match="429"):
            manager.execute_turn(_key("rl"), "hi", lambda: [sys.executable, str(agent), "rate_limit"], str(ROOT))
    finally:
        pool.shutdown()
    assert time.monotonic() - started < 15.0


def test_idle_timeout_is_timeout_error_and_eof_is_runtime_error(agent: Path) -> None:
    manager, pool = _manager(StreamJsonDriver(), idle=0.4)
    try:
        with pytest.raises(TimeoutError):
            manager.execute_turn(_key("t"), "hi", lambda: [sys.executable, str(agent), "silent"], str(ROOT))
        with pytest.raises(RuntimeError, match="ended before the terminal marker") as info:
            manager.execute_turn(_key("e"), "hi", lambda: [sys.executable, str(agent), "eof"], str(ROOT))
        assert not isinstance(info.value, TimeoutError)
    finally:
        pool.shutdown()


def test_review_profile_splits_resident_slots() -> None:
    manager, pool = _manager(StreamJsonDriver())
    argv = lambda: [sys.executable, str(FAKE_PROCESS), "--protocol", "stream-json"]  # noqa: E731
    try:
        first = manager.execute_turn(_key("same"), "a", argv, str(ROOT))
        again = manager.execute_turn(_key("same"), "b", argv, str(ROOT))
        other = manager.execute_turn(_key("same", "zero-canon"), "c", argv, str(ROOT))
        assert first.pid == again.pid != other.pid
    finally:
        pool.shutdown()


def test_claude_zero_canon_env_filters_settings_and_isolates_home(tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / ".claude").mkdir(parents=True)
    settings = {"env": {"A": "1"}, "hooks": {"Stop": []}, "permissions": {"allow": ["Bash"]}, "apiKeyHelper": "h"}
    (real / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    (real / ".claude.json").write_text(json.dumps({"userID": "u", "projects": {"/x": {}}}), encoding="utf-8")
    (real / ".claude" / "aeza-8788-ca.pem").write_text("PEM", encoding="utf-8")
    driver = ClaudeStreamJsonDriver()
    root = tmp_path / "iso"
    env = driver.build_zero_canon_env({"HOME": str(real), "PATH": "/bin", "CLAUDE_CONFIG_DIR": ""}, str(root))
    assert env["HOME"] == str(root) and env["CLAUDE_CONFIG_DIR"] == str(root / ".claude")
    assert env["PATH"] == "/bin"
    assert json.loads((root / ".claude" / "settings.json").read_text()) == {"apiKeyHelper": "h", "env": {"A": "1"}}
    assert json.loads((root / ".claude" / ".claude.json").read_text()) == {"userID": "u"}
    assert (root / ".claude" / "aeza-8788-ca.pem").read_text() == "PEM"
    argv = driver.build_zero_canon_argv(["claude", "--strict-mcp-config"], model="opus", effort="high")
    assert argv.count("--strict-mcp-config") == 1 and "--disable-slash-commands" in argv
    assert argv[argv.index("--model") + 1] == "opus" and argv[argv.index("--effort") + 1] == "high"
    assert "--model" not in driver.build_zero_canon_argv(["claude"], model="default", effort="")


def test_manager_runs_zero_canon_claude_in_isolated_ephemeral_home(agent: Path, tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / ".claude").mkdir(parents=True)
    (real / ".claude" / "settings.json").write_text('{"env": {"A": "1"}, "hooks": {"x": 1}}', encoding="utf-8")
    manager, pool = _manager(ClaudeStreamJsonDriver())
    try:
        result = manager.execute_turn(
            _key("zc", "zero-canon", "opus"), "hi",
            lambda: [sys.executable, str(agent), "claude"], str(ROOT),
            env={"HOME": str(real), "PATH": "/usr/bin:/bin"},
        )
    finally:
        pool.shutdown()
    info = json.loads("".join(chunk.text for chunk in result.chunks))
    assert info["home"] != str(real) and info["cfg"].endswith("/.claude")
    assert json.loads(info["settings"]) == {"env": {"A": "1"}}
    assert info["argv"][info["argv"].index("--model") + 1] == "opus"
    assert "--strict-mcp-config" in info["argv"] and "--disable-slash-commands" in info["argv"]
    assert not Path(info["home"]).exists()  # изолированный HOME удалён после хода
    assert [p for p in tmp_path.iterdir() if p.name.startswith("zc-")] == []


def test_codex_zero_canon_env_drops_mcp_and_agents_md(tmp_path: Path) -> None:
    real = tmp_path / "real" / ".codex"
    real.mkdir(parents=True)
    (real / "config.toml").write_text(
        'model = "gpt-x"\nnotify = ["say"]\n[mcp_servers.fs]\ncommand = "x"\n[plugins.p]\nenabled = true\n'
        '[profiles.fast]\nmodel = "m"\n', encoding="utf-8",
    )
    (real / "auth.json").write_text('{"token": "t"}', encoding="utf-8")
    (real / "AGENTS.md").write_text("canon", encoding="utf-8")
    driver = CodexAppServerDriver()
    root = tmp_path / "iso"
    env = driver.build_zero_canon_env({"HOME": str(tmp_path / "real"), "PATH": "/bin"}, str(root))
    assert env["HOME"] == str(root) and env["CODEX_HOME"] == str(root / ".codex")
    config = tomllib.loads((root / ".codex" / "config.toml").read_text())
    assert config == {"model": "gpt-x", "profiles": {"fast": {"model": "m"}}, "project_doc_max_bytes": 0}
    assert (root / ".codex" / "auth.json").read_text() == '{"token": "t"}'
    assert not (root / ".codex" / "AGENTS.md").exists()
    argv = driver.build_zero_canon_argv(["codex"], model="gpt-x", effort="high")
    assert argv[:2] == ["codex", "app-server"] and "model=\"gpt-x\"" in argv and "project_doc_max_bytes=0" in argv


def test_turn_error_sse_before_first_chunk_has_status_and_done() -> None:
    limited = build_turn_error(RuntimeError("claude_error status=429: rate limit"), live_sent=0)
    assert limited.status == 429 and limited.error_type == "rate_limit_error"
    assert limited.sse.endswith("data: [DONE]\n\n") and limited.sse.startswith("data: ")
    assert json.loads(limited.sse.split("\n\n")[0][len("data: "):]) == limited.body
    assert build_turn_error(TimeoutError("idle"), 0).status == 504
    assert build_turn_error(RuntimeError("boom"), 0).status == 502
    mid = build_turn_error(RuntimeError("boom"), live_sent=17)
    assert mid.status == 200 and mid.sse.endswith("data: [DONE]\n\n")
    assert len(build_turn_error(RuntimeError("x" * 900), 0, max_chars=40).message) == 40

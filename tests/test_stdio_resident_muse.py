"""Unit and integration tests for Meta Muse MSP v1 resident stdio support (ADR-0027)."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.stdio_drivers import (
    MuseMspDriver,
    build_affinity_key,
    resolve_chat_key,
    resolve_owner_hash,
)
from adapters.stdio_drivers.muse_codec import (
    MuseDecodedChunk,
    decode_msp_line,
    is_uuid7,
    uuid7,
)
from adapters.stdio_drivers.muse_env import (
    MUSE_ENV_ALLOWLIST,
    build_muse_env,
    resolve_pinned_path,
    verify_binary,
)
from adapters.stdio_resident_adapter import StdioResidentAdapter
from core.backend_adapter import Qualification, TurnResult
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_io import ResidentProcessHandle
from core.stdio_resident.process_reaper import is_pgid_alive, sweep_orphan_sandboxes, terminate_process_group
from core.stdio_resident.protocol_driver import DriverCapabilities, StdioProtocolDriver
from core.stdio_resident.rpc_drivers import create_protocol_driver
from core.stdio_resident.session_manager import SessionTurnMode, StdioSessionManager
from core.stdio_resident.types import SlotAffinityKey


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_valid_fingerprint_config(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    wrapper = tmp_path / "muse-wrapper"
    binary = tmp_path / "muse-bin"
    wrapper.write_bytes(b"#!/bin/sh\nexit 0\n")
    binary.write_bytes(b"\x7fELF-muse-binary")
    cfg: dict[str, Any] = {
        "fingerprint": {
            "version": "1.0.0",
            "wrapper_path": str(wrapper),
            "wrapper_sha256": _sha256(wrapper),
            "binary_path": str(binary),
            "binary_sha256": _sha256(binary),
        }
    }
    return wrapper, binary, cfg


def _write_mock_msp_script(path: Path) -> Path:
    script = """\
import json
import os
import sys

history = []
session_models = {}
while True:
    raw = sys.stdin.readline()
    if not raw:
        break
    line = raw.strip()
    if not line:
        continue
    msg = json.loads(line)
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}) + "\\n")
        sys.stdout.flush()
    elif method == "session/start":
        session_models[params.get("sessionId", "")] = str(params.get("modelId", ""))
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}) + "\\n")
        sys.stdout.flush()
    elif method == "turn/start":
        items = params.get("input") or []
        prompt = str(items[0].get("text", "")) if items and isinstance(items[0], dict) else str(params.get("prompt", ""))
        history.append(prompt)
        sid = str(params.get("sessionId", ""))
        model = str(params.get("model") or session_models.get(sid, ""))
        effort = str(params.get("reasoningEffort") or params.get("effort", ""))
        delta_text = (
            f"pid={os.getpid()}|history={','.join(history)}"
            f"|model={model}|effort={effort}"
            f"|session={sid}"
            f"|path={os.environ.get('PATH', '')}|proxy={os.environ.get('HTTP_PROXY', '')}"
            f"|tmpdir={os.environ.get('TMPDIR', '')}"
            f"|tmpdir_exists={os.path.isdir(os.environ.get('TMPDIR', ''))}"
        )
        delta = {
            "jsonrpc": "2.0",
            "method": "run.output.delta",
            "params": {"delta": delta_text},
        }
        done = {
            "jsonrpc": "2.0",
            "method": "run.terminal.completed",
            "params": {"stopReason": "end_turn"},
        }
        sys.stdout.write(json.dumps(delta) + "\\n")
        sys.stdout.write(json.dumps(done) + "\\n")
        sys.stdout.flush()
    elif method == "session/leave":
        ack = {"jsonrpc": "2.0", "id": req_id, "result": {}}
        sys.stdout.write(json.dumps(ack) + "\\n")
        sys.stdout.flush()
"""
    path.write_text(script, encoding="utf-8")
    return path


def _make_muse_adapter_with_mock_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch | None = None
) -> tuple[StdioResidentAdapter, MuseMspDriver]:
    _ = monkeypatch
    mock_script = _write_mock_msp_script(tmp_path / "mock_muse.py")
    digest = _sha256(mock_script)
    driver_cfg = {
        "fingerprint": {
            "version": "1",
            "wrapper_path": str(mock_script),
            "wrapper_sha256": digest,
            "binary_path": str(mock_script),
            "binary_sha256": digest,
        },
        "sandbox_flags": ["--sandbox"],
    }
    adapter = StdioResidentAdapter(
        "muse",
        {"options": {"protocol": "msp-v1", "sandbox_flags": ["--sandbox"]}},
        cli_argv=[sys.executable, str(mock_script)],
    )
    driver = MuseMspDriver(driver_cfg)
    adapter._driver = driver
    adapter._session_manager = StdioSessionManager(adapter._pool, driver, adapter._config)
    return adapter, driver


# ---------------------------------------------------------------------------
# 1. verify_binary, ~ resolution, infer_protocol, and StdioResidentAdapter.qualify()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ("wrapper_path", "wrapper_sha256", "binary_path", "binary_sha256"),
)
def test_verify_binary_missing_field_fails_closed(
    tmp_path: Path, missing_field: str
) -> None:
    _, _, cfg = _make_valid_fingerprint_config(tmp_path)
    del cfg["fingerprint"][missing_field]
    assert verify_binary(cfg) == (False, "binary_sha256_missing")


def test_verify_binary_missing_file_fails_closed(tmp_path: Path) -> None:
    wrapper, binary, cfg = _make_valid_fingerprint_config(tmp_path)
    binary.unlink()
    assert verify_binary(cfg) == (False, "binary_sha256_missing")

    binary.write_bytes(b"\x7fELF-muse-binary")
    wrapper.unlink()
    assert verify_binary(cfg) == (False, "binary_sha256_missing")


def test_verify_binary_sha256_mismatch(tmp_path: Path) -> None:
    _, _, cfg = _make_valid_fingerprint_config(tmp_path)
    cfg["fingerprint"]["binary_sha256"] = "0" * 64
    assert verify_binary(cfg) == (False, "binary_sha256_mismatch")

    _, _, cfg2 = _make_valid_fingerprint_config(tmp_path)
    cfg2["fingerprint"]["wrapper_sha256"] = "f" * 64
    assert verify_binary(cfg2) == (False, "binary_sha256_mismatch")


def test_resolve_pinned_path_and_verify_binary_tilde_and_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home_dir = tmp_path / "home"
    sub_dir = home_dir / "nested"
    real_dir = tmp_path / "real_target"
    sub_dir.mkdir(parents=True)
    real_dir.mkdir(parents=True)

    wrapper = real_dir / "muse-wrapper"
    binary = real_dir / "muse-bin"
    wrapper.write_bytes(b"wrapper-bytes")
    binary.write_bytes(b"binary-bytes")

    symlink_dir = home_dir / "link"
    os.symlink(real_dir, symlink_dir)
    monkeypatch.setenv("HOME", str(home_dir))

    resolved = resolve_pinned_path("~/nested/../link/muse-bin")
    assert resolved == os.path.realpath(str(binary))

    cfg = {
        "wrapper_path": "~/nested/../link/muse-wrapper",
        "wrapper_sha256": _sha256(wrapper),
        "binary_path": "~/nested/../link/muse-bin",
        "binary_sha256": _sha256(binary),
    }
    assert verify_binary(cfg) == (True, "")


def test_adapter_uses_infer_protocol_instead_of_substring_heuristic() -> None:
    unrelated = StdioResidentAdapter("custom", {"bridge": "not-muse-cli-wrapper"})
    by_id = StdioResidentAdapter("muse", {})
    by_wrapper = StdioResidentAdapter("custom", {"wrapper": "/opt/bin/muse-cli.sh"})
    try:
        assert unrelated._protocol == "stream-json"
        assert by_id._protocol == "msp-v1"
        assert by_wrapper._protocol == "msp-v1"
    finally:
        unrelated.shutdown(timeout_s=1.0)
        by_id.shutdown(timeout_s=1.0)
        by_wrapper.shutdown(timeout_s=1.0)


def test_adapter_qualify_returns_false_without_exception_on_invalid_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_MUSE_RESIDENT_ENABLED", "1")

    adapter = StdioResidentAdapter("muse", {"options": {"protocol": "msp-v1"}})
    try:
        # Unconfigured driver has missing sha256 -> fails closed cleanly
        missing_qual = adapter.qualify()
        assert missing_qual == Qualification(False, "binary_sha256_missing")

        _, _, cfg = _make_valid_fingerprint_config(tmp_path)
        cfg["fingerprint"]["binary_sha256"] = "deadbeef" * 8
        adapter._driver = MuseMspDriver(cfg)

        mismatch_qual = adapter.qualify()
        assert mismatch_qual == Qualification(False, "binary_sha256_mismatch")
    finally:
        adapter.shutdown(timeout_s=1.0)


# ---------------------------------------------------------------------------
# 2. Closed allowlist in build_muse_env
# ---------------------------------------------------------------------------


def test_build_muse_env_filters_secrets_and_keeps_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = str(tmp_path / "sb")
    trusted_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": "/tmp",
        "HTTP_PROXY": "http://proxy:8080",
        "HTTPS_PROXY": "https://proxy:8443",
        "NO_PROXY": "localhost",
        "MUSE_PROVIDER": "internal",
        "BRIDGE_KEY": "secret-bridge-key",
        "OPENAI_API_KEY": "sk-secret-openai",
        "MUSE_ARBITRARY_SECRET": "top-secret-value",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
    }
    for k, v in trusted_env.items():
        monkeypatch.setenv(k, v)

    env = build_muse_env(
        {"PATH": "/evil", "HTTP_PROXY": "http://evil"},
        "/opt/muse/bin",
        turn_sandbox=sandbox,
    )

    for forbidden in (
        "BRIDGE_KEY",
        "OPENAI_API_KEY",
        "MUSE_ARBITRARY_SECRET",
        "AWS_SECRET_ACCESS_KEY",
    ):
        assert forbidden not in env

    for key in MUSE_ENV_ALLOWLIST:
        if key != "TMPDIR":
            assert env[key] == trusted_env[key]
    assert env["MUSE_BIN_PATH"] == "/opt/muse/bin"
    assert env["TMPDIR"] == sandbox


def test_client_env_cannot_override_path_or_http_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_MUSE_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:/usr/bin:/bin")
    monkeypatch.setenv("HTTP_PROXY", "http://safe-proxy:8080")

    adapter, driver = _make_muse_adapter_with_mock_script(tmp_path, monkeypatch)
    driver_env = driver.build_env({"PATH": "/evil", "HTTP_PROXY": "http://evil"})
    assert driver_env["PATH"] != "/evil"
    assert driver_env["HTTP_PROXY"] == "http://safe-proxy:8080"

    seen_envs: list[Any] = []
    orig_stream = adapter._session_manager.execute_turn_stream

    def _spy_stream(*args: Any, **kwargs: Any) -> Iterator[Any]:
        seen_envs.append(kwargs.get("env"))
        return orig_stream(*args, **kwargs)

    monkeypatch.setattr(adapter._session_manager, "execute_turn_stream", _spy_stream)
    try:
        deltas = list(
            adapter.execute_chat(
                {
                    "chat_key": "env-chat",
                    "cwd": str(tmp_path),
                    "prompt": "check-env",
                    "env": {"PATH": "/evil", "HTTP_PROXY": "http://evil"},
                },
                auth_owner_hash="token_env",
            )
        )
        content = "".join(d["choices"][0]["delta"].get("content", "") for d in deltas)
        assert seen_envs == [None]
        assert "/evil" not in content
        assert "http://evil" not in content
    finally:
        adapter.shutdown(timeout_s=2.0)


# ---------------------------------------------------------------------------
# 3. MuseMspDriver and muse_codec
# ---------------------------------------------------------------------------


def test_msp_v1_registered_in_create_protocol_driver() -> None:
    driver = create_protocol_driver("msp-v1")
    assert isinstance(driver, MuseMspDriver)
    assert driver.capabilities.protocol_name == "msp-v1"
    assert driver.capabilities.supports_multi_turn is True
    assert driver.capabilities.supports_soft_cancel is False


def test_muse_driver_sandbox_args_and_build_argv() -> None:
    default_driver = MuseMspDriver()
    assert default_driver.build_sandbox_args() == ["--sandbox"]

    hardened_flags = [
        "--disable-write",
        "--disable-shell",
        "--disable-request-user-input",
        "--no-session-log",
    ]
    configured_driver = MuseMspDriver({"sandbox_flags": hardened_flags})
    assert configured_driver.build_sandbox_args() == hardened_flags

    argv = configured_driver.build_argv(
        ["/usr/local/bin/muse-wrapper", "--disable-write"],
        {"cli_args": ["--extra-opt"]},
    )
    assert argv == [
        "/usr/local/bin/muse-wrapper",
        "--disable-write",
        "--disable-shell",
        "--disable-request-user-input",
        "--no-session-log",
        "--extra-opt",
    ]


def test_muse_driver_build_argv_pins_wrapper_and_dedups_sandbox_flags(
    tmp_path: Path,
) -> None:
    wrapper, _, cfg = _make_valid_fingerprint_config(tmp_path)
    cfg["sandbox_flags"] = ["--disable-write", "--sandbox"]
    cfg["cli_args"] = ["--stdio"]
    driver = MuseMspDriver(cfg)

    assert driver.build_argv([], {}) == [
        resolve_pinned_path(str(wrapper)),
        "--disable-write",
        "--sandbox",
        "--stdio",
    ]

    pinned = driver.build_argv(
        ["/untrusted/override/muse-wrapper", "--disable-write"],
        {"cli_args": ["--disable-write", "--extra"]},
    )
    assert pinned == [
        resolve_pinned_path(str(wrapper)),
        "--disable-write",
        "--sandbox",
        "--extra",
    ]

    cfg["fingerprint"]["binary_sha256"] = "0" * 64
    tampered_driver = MuseMspDriver(cfg)
    with pytest.raises(RuntimeError, match="binary_sha256_mismatch"):
        tampered_driver.build_argv(["/untrusted/override/muse-wrapper"], {})


def test_muse_driver_run_handshake_sends_initialize_waits_ack_and_sends_initialized() -> None:
    class _FakeHandle:
        def __init__(self, stdout_bytes: bytes) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(stdout_bytes)

        def poll(self) -> int | None:
            return None

    driver = MuseMspDriver()
    notif = json.dumps({"jsonrpc": "2.0", "method": "log", "params": {}}).encode() + b"\n"
    ack = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}).encode() + b"\n"
    ok_handle = _FakeHandle(notif + ack)
    assert driver.run_handshake(ok_handle, timeout_s=1.0) is True

    lines = [json.loads(line) for line in ok_handle.stdin.getvalue().decode("utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["jsonrpc"] == "2.0"
    assert lines[0]["method"] == "initialize"
    assert lines[0]["id"] == 1
    assert lines[0]["params"]["clientInfo"]["name"] == "cli_agent_bridge"
    assert lines[1] == {"jsonrpc": "2.0", "method": "initialized"}

    err_ack = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "init failed"}}).encode() + b"\n"
    err_handle = _FakeHandle(err_ack)
    assert driver.run_handshake(err_handle, timeout_s=1.0) is False
    assert len(err_handle.stdin.getvalue().decode("utf-8").splitlines()) == 1
    assert driver.run_handshake(_FakeHandle(b""), timeout_s=0.1) is False


def test_muse_driver_prepare_turn_sends_session_start_with_uuid7_and_waits_ack() -> None:
    class _FakeHandle:
        def __init__(self, stdout_bytes: bytes) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(stdout_bytes)

        def poll(self) -> int | None:
            return None

    driver = MuseMspDriver()
    ack = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode() + b"\n"
    ok_handle = _FakeHandle(ack)
    ctx: dict[str, Any] = {"session_id": "non-uuid-chat-key", "model": "muse-pro-1"}
    assert driver.prepare_turn(ok_handle, ctx, timeout_s=1.0) is True

    sid = ctx.get("_msp_session_id")
    assert is_uuid7(sid)
    assert driver._last_session_id == sid

    sent = json.loads(ok_handle.stdin.getvalue().decode("utf-8"))
    assert sent["jsonrpc"] == "2.0"
    assert sent["method"] == "session/start"
    assert sent["id"] == 1
    assert sent["params"]["sessionId"] == sid
    assert is_uuid7(sent["params"]["commandId"])
    assert sent["params"]["modelId"] == "muse-pro-1"
    assert sent["params"]["approvalMode"] == "denyUnmatched"

    err_ack = json.dumps({"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "bad"}}).encode() + b"\n"
    assert driver.prepare_turn(_FakeHandle(err_ack), {}, timeout_s=1.0) is False
    assert driver.prepare_turn(_FakeHandle(b""), {}, timeout_s=0.1) is False


def test_muse_driver_encode_turn_formats_turn_start_with_input_and_uuid7() -> None:
    driver = MuseMspDriver()
    sid = uuid7()
    encoded = driver.encode_turn("hello msp", {"_msp_session_id": sid, "effort": "high"})
    sent = json.loads(encoded.decode("utf-8"))

    assert sent["jsonrpc"] == "2.0"
    assert sent["method"] == "turn/start"
    assert isinstance(sent["id"], int)
    assert sent["params"]["sessionId"] == sid
    assert sent["params"]["input"] == [{"type": "text", "text": "hello msp"}]
    assert sent["params"]["reasoningEffort"] == "high"
    assert is_uuid7(sent["params"]["commandId"])


def test_perform_turn_teardown_sends_session_leave_and_waits_ack() -> None:
    class _FakeHandle:
        def __init__(self, stdout_bytes: bytes, rc: int | None = None) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(stdout_bytes)
            self._rc = rc

        def poll(self) -> int | None:
            return self._rc

    driver = MuseMspDriver()
    sid = uuid7()
    ack_line = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode() + b"\n"
    ok_handle = _FakeHandle(ack_line)
    assert driver.perform_turn_teardown(ok_handle, {"_msp_session_id": sid}, timeout_s=1.0) is True

    sent = json.loads(ok_handle.stdin.getvalue().decode("utf-8"))
    assert sent["jsonrpc"] == "2.0"
    assert sent["method"] == "session/leave"
    assert sent["id"] == 1
    assert sent["params"]["sessionId"] == sid
    assert sent["params"]["stop"] is True
    assert is_uuid7(sent["params"]["commandId"])

    # Resolves _last_session_id when turn_context only carries a non-UUIDv7 session_id
    ack_last = json.dumps({"jsonrpc": "2.0", "id": 2, "result": {}}).encode() + b"\n"
    last_handle = _FakeHandle(ack_last)
    assert driver.perform_turn_teardown(last_handle, {"session_id": "chat-key"}, timeout_s=1.0) is True
    sent_last = json.loads(last_handle.stdin.getvalue().decode("utf-8"))
    assert sent_last["params"]["sessionId"] == sid

    # Fail-closed on error response, EOF, dead process, and None handle
    err_line = json.dumps(
        {"jsonrpc": "2.0", "id": 3, "error": {"code": -32603, "message": "boom"}}
    ).encode() + b"\n"
    assert driver.perform_turn_teardown(_FakeHandle(err_line), {"_msp_session_id": sid}, timeout_s=1.0) is False
    assert driver.perform_turn_teardown(_FakeHandle(b""), {"_msp_session_id": sid}, timeout_s=0.1) is False
    assert driver.perform_turn_teardown(_FakeHandle(ack_line, rc=1), {"_msp_session_id": sid}, timeout_s=1.0) is False
    assert driver.perform_turn_teardown(None, {}, timeout_s=1.0) is False


def test_perform_turn_teardown_skips_diagnostic_non_json_lines() -> None:
    class _FakeHandle:
        def __init__(self, stdout_bytes: bytes) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(stdout_bytes)

        def poll(self) -> int | None:
            return None

    assert MuseMspDriver._check_teardown_ack("diagnostic non-json line", "cmd-diag") is None
    assert MuseMspDriver._check_teardown_ack("not-json", 42) is None

    driver = MuseMspDriver()
    sid = uuid7()
    ack_line = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode() + b"\n"
    stdout_bytes = b"[diag] worker flushing buffers\nplain text status\n" + ack_line
    handle = _FakeHandle(stdout_bytes)
    assert driver.perform_turn_teardown(handle, {"_msp_session_id": sid}, timeout_s=1.0) is True

    # Diagnostic lines alone without an ack before EOF still fail closed
    eof_only = _FakeHandle(b"[diag] only diagnostic output\n")
    assert driver.perform_turn_teardown(eof_only, {"_msp_session_id": sid}, timeout_s=0.2) is False


def test_decode_msp_line_turn_completed_and_item_completed() -> None:
    ok_turn = decode_msp_line(json.dumps({
        "jsonrpc": "2.0",
        "method": "turn/completed",
        "params": {"stopReason": "end_turn", "text": "final answer"},
    }))
    assert ok_turn.is_terminal is True
    assert ok_turn.error is None
    assert ok_turn.text == "final answer"
    assert ok_turn.is_tool_stop is False

    rate_limited_turn = decode_msp_line(json.dumps({
        "jsonrpc": "2.0",
        "method": "turn/completed",
        "params": {"terminal": "failed", "error": {"code": 429, "message": "too many requests"}},
    }))
    assert isinstance(rate_limited_turn, MuseDecodedChunk)
    assert rate_limited_turn.is_terminal is True
    assert rate_limited_turn.error == "rate_limited"

    user_item = decode_msp_line(json.dumps({
        "jsonrpc": "2.0",
        "method": "item/completed",
        "params": {"item": {"type": "userMessage", "text": "echoed user prompt"}},
    }))
    assert user_item.text == ""
    assert user_item.reasoning == ""
    assert user_item.is_terminal is False
    assert getattr(user_item, "error", None) is None

    assistant_item = decode_msp_line(json.dumps({
        "jsonrpc": "2.0",
        "method": "item/completed",
        "params": {"item": {"type": "assistantMessage", "text": "assistant reply"}},
    }))
    assert assistant_item.text == "assistant reply"
    assert assistant_item.is_terminal is False


def test_session_manager_real_resident_process_handle_teardown_uses_read_line(
    tmp_path: Path,
) -> None:
    fake_script = _write_mock_msp_script(tmp_path / "fake_muse_e2e.py")
    digest = _sha256(fake_script)
    driver = MuseMspDriver({
        "fingerprint": {
            "version": "1",
            "wrapper_path": str(fake_script),
            "wrapper_sha256": digest,
            "binary_path": str(fake_script),
            "binary_sha256": digest,
        },
        "sandbox_flags": ["--sandbox"],
    })

    teardown_calls: list[tuple[bool, bool]] = []
    orig_teardown = driver.perform_turn_teardown

    def _spy_teardown(handle: Any, turn_context: Any, timeout_s: float = 2.0) -> bool:
        ok = orig_teardown(handle, turn_context, timeout_s=timeout_s)
        teardown_calls.append((isinstance(handle, ResidentProcessHandle), ok))
        return ok

    driver.perform_turn_teardown = _spy_teardown  # type: ignore[method-assign]

    class _RealHandlePool:
        def __init__(self) -> None:
            self.handle: ResidentProcessHandle | None = None
            self.released: list[tuple[str, bool]] = []

        def acquire(
            self,
            affinity_key: SlotAffinityKey,
            argv_builder: Any,
            cwd: str,
            env: Any = None,
            is_ephemeral: bool = False,
        ) -> SimpleNamespace:
            _ = is_ephemeral
            self.handle = ResidentProcessHandle.spawn(argv_builder(), cwd, env=env)
            return SimpleNamespace(
                slot_id="slot-real-1",
                affinity_key=affinity_key,
                handle=self.handle,
                lease_id="lease-real-1",
            )

        def release(
            self,
            slot_id: str,
            success: bool = True,
            cancel: bool = False,
            lease_id: str | None = None,
        ) -> None:
            _ = (success, lease_id)
            self.released.append((slot_id, cancel))

    pool = _RealHandlePool()
    manager = StdioSessionManager(pool, driver, StdioPoolConfig())  # type: ignore[arg-type]
    key = build_affinity_key("owner-e2e", "chat-e2e", "muse", "m1", "medium", str(tmp_path))

    try:
        result = manager.execute_turn(
            key,
            "hello-real",
            lambda: [sys.executable, str(fake_script)],
            str(tmp_path),
            turn_context={"session_id": "chat-e2e", "model": "m1", "effort": "medium"},
        )
        assert result.mode == SessionTurnMode.COLD
        assert any("history=hello-real" in c.text for c in result.chunks)
        assert teardown_calls == [(True, True)]
        assert pool.released == [("slot-real-1", False)]
    finally:
        if pool.handle is not None:
            pool.handle.terminate_gracefully(grace_s=0.2, timeout_s=2.0)


def test_decode_msp_line_error_precedes_approval_reply_bytes() -> None:
    # approval.request with error must return error and suppress reply_bytes
    err_frame = json.dumps({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "approval.request",
        "params": {"approvalId": "ap-1", "error": "forbidden"},
    })
    decoded_err = decode_msp_line(err_frame)
    assert isinstance(decoded_err, MuseDecodedChunk)
    assert decoded_err.error == "auth_error"
    assert decoded_err.is_terminal is True
    assert decoded_err.reply_bytes is None

    # Normal approval.request produces denial reply_bytes
    ok_frame = json.dumps({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "approval.request",
        "params": {"approvalId": "ap-2", "sessionId": "s1"},
    })
    decoded_ok = decode_msp_line(ok_frame)
    assert isinstance(decoded_ok, MuseDecodedChunk)
    assert decoded_ok.error is None
    assert decoded_ok.reply_bytes is not None
    reply_obj = json.loads(decoded_ok.reply_bytes.decode("utf-8"))
    assert reply_obj["method"] == "approval/decide"
    assert reply_obj["params"]["choiceId"] == "deny"


def test_session_manager_handles_error_before_reply_bytes_without_write() -> None:
    writes: list[bytes] = []

    class _MockHandle:
        def __init__(self) -> None:
            self.pid = 99999
            self.generation = 0
            self._pgid = 99999
            self._start_time = ""
            self._pgid_dead = True

        def write(self, data: bytes) -> None:
            writes.append(data)

        def read_line(self, timeout_s: float | None = None) -> SimpleNamespace:
            return SimpleNamespace(line='{"dummy": true}', generation=0, pid=self.pid)

    class _MockPool:
        def __init__(self) -> None:
            self.released: list[tuple[str, bool]] = []
            self.handle = _MockHandle()

        def acquire(
            self,
            affinity_key: SlotAffinityKey,
            argv_builder: Any,
            cwd: str,
            env: Any = None,
            is_ephemeral: bool = False,
        ) -> SimpleNamespace:
            return SimpleNamespace(
                slot_id="slot-1",
                affinity_key=affinity_key,
                handle=self.handle,
                lease_id="lease-1",
            )

        def release(
            self,
            slot_id: str,
            success: bool = True,
            cancel: bool = False,
            lease_id: str | None = None,
        ) -> None:
            self.released.append((slot_id, cancel))

    class _BothErrorAndReplyDriver(StdioProtocolDriver):
        @property
        def capabilities(self) -> DriverCapabilities:
            return DriverCapabilities(protocol_name="msp-v1")

        def build_argv(self, base_argv: list[str], options: Any) -> list[str]:
            return list(base_argv)

        def encode_turn(self, prompt: str, turn_context: Any = None) -> bytes:
            return b'{"turn":"start"}\n'

        def decode_line(self, raw_line: str) -> MuseDecodedChunk:
            return MuseDecodedChunk(
                error="auth_error",
                reply_bytes=b'{"jsonrpc":"2.0","method":"approval/decide"}\n',
                is_terminal=True,
            )

        def is_terminal(self, raw_line: str, decoded: Any) -> bool:
            return True

        def is_tool_stop(self, raw_line: str, decoded: Any) -> bool:
            return False

        def build_cancel_payload(self) -> bytes | None:
            return None

    pool = _MockPool()
    manager = StdioSessionManager(pool, _BothErrorAndReplyDriver(), StdioPoolConfig())  # type: ignore[arg-type]
    key = build_affinity_key("owner-1", "chat-1", "muse", "m", "medium", os.getcwd())

    with pytest.raises(RuntimeError, match="auth_error"):
        manager.execute_turn(key, "hi", lambda: ["mock"], os.getcwd())

    # Only encode_turn was written; reply_bytes was never written
    assert writes == [b'{"turn":"start"}\n']
    assert pool.released == [("slot-1", True)]


# ---------------------------------------------------------------------------
# 4. resolve_chat_key, fail-closed auth, and execute_turn forwarding
# ---------------------------------------------------------------------------


def test_resolve_chat_key_validation_and_ephemeral() -> None:
    with pytest.raises(ValueError, match="conflicting_session_identifiers"):
        resolve_chat_key({"chat_key": "chat-a", "session_id": "chat-b"})

    with pytest.raises(ValueError, match="conflicting_session_identifiers"):
        resolve_chat_key({"chat_key": "chat-a", "conversation_id": "chat-b"})

    assert resolve_chat_key({"chat_key": "chat-a", "session_id": "chat-a"}) == (
        "chat-a",
        False,
    )

    for bad_id in ("../etc/passwd", "a/b", "", "x" * 129, "bad id", 12345):
        with pytest.raises(ValueError, match="invalid_session_id"):
            resolve_chat_key({"session_id": bad_id})

    assert resolve_chat_key({"chat_key": "chat-ok", "session_id": None}) == (
        "chat-ok",
        False,
    )

    eph_none, is_eph_none = resolve_chat_key({"session_id": None})
    assert is_eph_none is True
    assert len(eph_none) == 32

    eph_empty, is_eph_empty = resolve_chat_key({})
    assert is_eph_empty is True
    assert len(eph_empty) == 32
    assert eph_none != eph_empty


def test_resolve_owner_hash_ignores_client_owner_and_requires_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Client-supplied owner_hash and _auth_owner_hash must be ignored and fail closed for msp-v1
    with pytest.raises(PermissionError, match="auth_required_for_resident_pool"):
        resolve_owner_hash({"owner_hash": "spoofed-client"}, "msp-v1")

    with pytest.raises(PermissionError, match="auth_required_for_resident_pool"):
        resolve_owner_hash({"_auth_owner_hash": "evil", "owner_hash": "spoofed"}, "msp-v1")

    assert (
        resolve_owner_hash(
            {"_auth_owner_hash": "evil", "owner_hash": "spoofed"},
            "msp-v1",
            trusted_owner_hash="server-token-hash",
        )
        == "server-token-hash"
    )

    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    adapter = StdioResidentAdapter(
        "muse",
        {"options": {"protocol": "msp-v1"}},
        cli_argv=[sys.executable, "-c", "pass"],
    )
    try:
        with pytest.raises(PermissionError, match="auth_required_for_resident_pool"):
            list(adapter.execute_chat({"owner_hash": "spoofed", "cwd": str(tmp_path), "prompt": "hi"}))

        with pytest.raises(PermissionError, match="auth_required_for_resident_pool"):
            list(adapter.execute_chat({"_auth_owner_hash": "evil", "cwd": str(tmp_path), "prompt": "hi"}))

        with pytest.raises(PermissionError, match="auth_required_for_resident_pool"):
            list(adapter.execute_chat(SimpleNamespace(owner_hash="spoofed", cwd=str(tmp_path), prompt="hi")))

        with pytest.raises(PermissionError, match="auth_required_for_resident_pool"):
            list(adapter.execute_chat(SimpleNamespace(_auth_owner_hash="evil", cwd=str(tmp_path), prompt="hi")))
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_turn_context_cannot_override_session_id_cwd_or_delete_forbidden_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_MUSE_RESIDENT_ENABLED", "1")

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    forbidden_dir = tmp_path / "forbidden"
    forbidden_dir.mkdir()
    sentinel = forbidden_dir / "keep.txt"
    sentinel.write_text("untouched", encoding="utf-8")

    adapter, _ = _make_muse_adapter_with_mock_script(tmp_path, monkeypatch)
    captured_calls: list[dict[str, Any]] = []
    orig_stream = adapter._session_manager.execute_turn_stream

    def _spy_stream(*args: Any, **kwargs: Any) -> Iterator[Any]:
        captured_calls.append({"args": args, "kwargs": kwargs})
        return orig_stream(*args, **kwargs)

    monkeypatch.setattr(adapter._session_manager, "execute_turn_stream", _spy_stream)
    try:
        deltas = list(
            adapter.execute_chat(
                {
                    "chat_key": "legit-chat",
                    "cwd": str(work_dir),
                    "prompt": "probe-turn-context",
                    "turn_context": {
                        "turn_sandbox": str(forbidden_dir),
                        "session_id": "hijack",
                        "cwd": "/",
                    },
                },
                auth_owner_hash="token_tc",
            )
        )
        content = "".join(d["choices"][0]["delta"].get("content", "") for d in deltas)
        assert len(captured_calls) == 1
        call_kwargs = captured_calls[0]["kwargs"]
        assert call_kwargs["cwd"] == str(work_dir)
        assert call_kwargs["affinity_key"].chat_key == "legit-chat"
        assert call_kwargs["turn_context"].get("session_id") == "legit-chat"
        assert call_kwargs["turn_context"].get("cwd") != "/"
        m = re.search(r"session=([0-9a-f-]+)", content)
        assert m is not None and is_uuid7(m.group(1))
        assert adapter._driver._last_session_id == m.group(1)
        assert "session=hijack" not in content
        assert forbidden_dir.exists()
        assert sentinel.read_text(encoding="utf-8") == "untouched"
    finally:
        adapter.shutdown(timeout_s=2.0)


def test_execute_turn_forwards_model_effort_auth_and_keeps_missing_chat_key_ephemeral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_MUSE_RESIDENT_ENABLED", "1")

    adapter, _ = _make_muse_adapter_with_mock_script(tmp_path, monkeypatch)
    captured_calls: list[dict[str, Any]] = []
    orig_stream = adapter._session_manager.execute_turn_stream

    def _spy_stream(*args: Any, **kwargs: Any) -> Iterator[Any]:
        captured_calls.append({"args": args, "kwargs": kwargs})
        return orig_stream(*args, **kwargs)

    monkeypatch.setattr(adapter._session_manager, "execute_turn_stream", _spy_stream)

    sse_events: list[tuple[str, str]] = []
    ctx = SimpleNamespace(
        model="muse-custom-model",
        effort="high",
        cwd=str(tmp_path),
        prompt="hello-turn",
        fwd_env={"PATH": "/evil"},
        turn_id="turn-123",
        rid="rid-456",
        key_hash="trusted-turn-owner",
    )
    try:
        result = adapter.execute_turn(ctx, lambda kind, val: sse_events.append((kind, val)))  # type: ignore[arg-type]
        assert len(captured_calls) == 1
        call_kwargs = captured_calls[0]["kwargs"]
        affinity_key = call_kwargs["affinity_key"]
        turn_context = call_kwargs["turn_context"]

        assert len(adapter._pool._slots) == 0
        assert affinity_key.owner_hash == "trusted-turn-owner"
        assert affinity_key.chat_key not in ("turn-123", "rid-456")
        assert call_kwargs["env"] is None

        assert turn_context["model"] == "muse-custom-model"
        assert turn_context["effort"] == "high"
        assert turn_context["session_id"] == affinity_key.chat_key

        assert "model=muse-custom-model" in result.text
        assert "effort=high" in result.text
        m = re.search(r"session=([0-9a-f-]+)", result.text)
        assert m is not None and is_uuid7(m.group(1))
        assert adapter._driver._last_session_id == m.group(1)
        assert sse_events == [("content", result.text)]
    finally:
        adapter.shutdown(timeout_s=2.0)


def test_execute_turn_returns_error_result_on_stream_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, _ = _make_muse_adapter_with_mock_script(tmp_path, monkeypatch)

    def _failing_stream(*_args: Any, **_kwargs: Any) -> Iterator[Any]:
        raise RuntimeError("rate_limited")
        yield

    monkeypatch.setattr(adapter._session_manager, "execute_turn_stream", _failing_stream)
    ctx = SimpleNamespace(
        model="muse-1",
        effort="medium",
        cwd=str(tmp_path),
        prompt="hello",
        fwd_env=None,
        key_hash="trusted-turn-owner",
    )
    try:
        result = adapter.execute_turn(ctx, None)  # type: ignore[arg-type]
        assert result == TurnResult(state="error", rc=1, err="rate_limited")
    finally:
        adapter.shutdown(timeout_s=1.0)


# ---------------------------------------------------------------------------
# 5. Canary isolation (token_A vs token_B and turn A/B)
# ---------------------------------------------------------------------------


def test_canary_isolation_between_principals_with_same_chat_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_MUSE_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_STDIO_MAX_SLOTS", "4")
    monkeypatch.setenv("BRIDGE_STDIO_MAX_SLOTS_PER_PRINCIPAL", "2")

    adapter, _ = _make_muse_adapter_with_mock_script(tmp_path, monkeypatch)

    def _run_chat(owner_hash: str, prompt: str) -> str:
        deltas = list(
            adapter.execute_chat(
                {
                    "chat_key": "shared-chat-key",
                    "model": "muse-1",
                    "effort": "medium",
                    "cwd": str(tmp_path),
                    "prompt": prompt,
                },
                auth_owner_hash=owner_hash,
            )
        )
        return "".join(
            d["choices"][0]["delta"].get("content", "") for d in deltas
        )

    try:
        out_a1 = _run_chat("token_A", "canary-secret-A1")
        out_a2 = _run_chat("token_A", "followup-A2")
        out_b1 = _run_chat("token_B", "probe-B1")

        pid_a1 = out_a1.split("|", 1)[0]
        pid_a2 = out_a2.split("|", 1)[0]
        pid_b1 = out_b1.split("|", 1)[0]

        assert pid_a1.startswith("pid=")
        # Same principal + chat_key reuses the hot slot
        assert pid_a2 == pid_a1
        assert "canary-secret-A1" in out_a2
        assert "followup-A2" in out_a2

        # Different principal with identical chat_key gets a separate slot/PID and no leakage
        assert pid_b1 != pid_a1
        assert "canary-secret-A1" not in out_b1
        assert "followup-A2" not in out_b1
        assert "history=probe-B1" in out_b1
    finally:
        adapter.shutdown(timeout_s=2.0)


def test_hot_turn_tmpdir_remains_valid_and_not_deleted_turn_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_RESIDENT_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_MUSE_RESIDENT_ENABLED", "1")
    pool_tmp = tmp_path / "pool_tmpdir"
    pool_tmp.mkdir()
    monkeypatch.setenv("TMPDIR", str(pool_tmp))

    adapter, _ = _make_muse_adapter_with_mock_script(tmp_path, monkeypatch)

    def _run_turn(prompt: str) -> dict[str, str]:
        deltas = list(
            adapter.execute_chat(
                {
                    "chat_key": "hot-tmpdir-chat",
                    "model": "muse-1",
                    "effort": "medium",
                    "cwd": str(tmp_path),
                    "prompt": prompt,
                },
                auth_owner_hash="token_tmpdir",
            )
        )
        text = "".join(d["choices"][0]["delta"].get("content", "") for d in deltas)
        return dict(item.split("=", 1) for item in text.split("|") if "=" in item)

    try:
        cold_fields = _run_turn("turn-1")
        hot_fields = _run_turn("turn-2")

        assert hot_fields["pid"] == cold_fields["pid"]
        assert hot_fields["history"] == "turn-1,turn-2"
        assert hot_fields["tmpdir"] == str(pool_tmp)
        assert hot_fields["tmpdir_exists"] == "True"
        assert Path(hot_fields["tmpdir"]).is_dir()
        assert not Path(hot_fields["tmpdir"]).name.startswith("turn-")
    finally:
        adapter.shutdown(timeout_s=2.0)


# ---------------------------------------------------------------------------
# 6. process_reaper, process_io, and config
# ---------------------------------------------------------------------------


def test_terminate_process_group_already_dead_and_real_child() -> None:
    class _DeadSentinelProc:
        def poll(self) -> int:
            raise AssertionError("poll should not be called when already_dead=True")

    assert terminate_process_group(_DeadSentinelProc(), 12345, "", already_dead=True) is True
    assert terminate_process_group(None, 0, "", already_dead=False) is True

    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        pgid = proc.pid
        start_time = ""
        assert terminate_process_group(proc, pgid, start_time, cancel_grace_s=0.1) is True
        assert proc.poll() is not None
        assert not _is_alive_after_reap(pgid)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2.0)


def _is_alive_after_reap(pgid: int) -> bool:
    return is_pgid_alive(pgid)


def test_sweep_orphan_sandboxes_removes_unlocked_lock_and_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    orphan_dir = tmp_path / "turn-stale-123"
    orphan_dir.mkdir()
    (orphan_dir / "leftover.txt").write_text("stale", encoding="utf-8")
    orphan_lock = tmp_path / "turn-stale-123.lock"
    orphan_lock.write_text("{}", encoding="utf-8")

    swept = sweep_orphan_sandboxes(tempfile.gettempdir())
    assert swept == 1
    assert not orphan_lock.exists()
    assert not orphan_dir.exists()


def test_sweep_orphan_sandboxes_respects_active_flock(tmp_path: Path) -> None:
    orphan_dir = tmp_path / "turn-orphan"
    orphan_dir.mkdir()
    (orphan_dir / "artifact.txt").write_text("stale", encoding="utf-8")
    orphan_lock = tmp_path / "turn-orphan.lock"
    orphan_lock.write_text("{}", encoding="utf-8")

    active_dir = tmp_path / "turn-active"
    active_dir.mkdir()
    (active_dir / "keep.txt").write_text("live", encoding="utf-8")
    active_lock = tmp_path / "turn-active.lock"
    active_lock.write_text("{}", encoding="utf-8")

    locker_code = (
        "import fcntl, sys\n"
        "f = open(sys.argv[1], 'r+')\n"
        "fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "sys.stdout.write('locked\\n')\n"
        "sys.stdout.flush()\n"
        "sys.stdin.readline()\n"
    )
    locker = subprocess.Popen(
        [sys.executable, "-c", locker_code, str(active_lock)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert locker.stdout is not None
        ready = locker.stdout.readline().strip()
        assert ready == "locked"

        swept = sweep_orphan_sandboxes(str(tmp_path))
        assert swept == 1
        assert not orphan_dir.exists()
        assert not orphan_lock.exists()
        assert active_dir.exists()
        assert active_lock.exists()
    finally:
        if locker.stdin is not None:
            try:
                locker.stdin.write("\n")
                locker.stdin.flush()
            except OSError:
                pass
        locker.wait(timeout=2.0)


def test_resident_process_handle_io_and_output_limit(tmp_path: Path) -> None:
    echo_script = (
        "import sys\n"
        "for line in sys.stdin:\n"
        "    sys.stderr.write('err:' + line)\n"
        "    sys.stderr.flush()\n"
        "    sys.stdout.write('out:' + line)\n"
        "    sys.stdout.flush()\n"
    )
    handle = ResidentProcessHandle.spawn(
        [sys.executable, "-c", echo_script], cwd=str(tmp_path), max_output_bytes=2048
    )
    try:
        handle.write(b"hello\n")
        deadline = time.monotonic() + 2.0
        seen_stdout: list[str] = []
        while time.monotonic() < deadline and not seen_stdout:
            tagged = handle.read_line(timeout_s=0.5)
            if tagged is not None and not tagged.is_stderr:
                seen_stdout.append(tagged.line)
        assert seen_stdout == ["out:hello"]
        assert handle.advance_generation() == 1
    finally:
        rc = handle.terminate_gracefully(grace_s=0.2, timeout_s=2.0)
        assert isinstance(rc, int)
        assert "err:hello" in handle.stderr_tail()

    # Exceeding max_output_bytes triggers output_limit_exceeded
    overflow_handle = ResidentProcessHandle.spawn(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 2048 + '\\n'); sys.stdout.flush()"],
        cwd=str(tmp_path),
        max_output_bytes=1024,
    )
    try:
        with pytest.raises(RuntimeError, match="output_limit_exceeded"):
            overflow_handle.read_line(timeout_s=2.0)
    finally:
        overflow_handle.terminate_gracefully(grace_s=0.1, timeout_s=2.0)


def test_stdio_pool_config_from_env() -> None:
    defaults = StdioPoolConfig.from_env({})
    assert defaults.enabled is False
    assert defaults.max_slots == 4
    assert defaults.max_slots_per_principal == 4
    assert defaults.max_ephemeral_slots == 2
    assert defaults.max_turn_output_bytes == 4194304

    custom = StdioPoolConfig.from_env({
        "BRIDGE_STDIO_RESIDENT_ENABLED": "true",
        "BRIDGE_STDIO_MAX_SLOTS": "6",
        "BRIDGE_STDIO_MAX_SLOTS_PER_PRINCIPAL": "3",
        "BRIDGE_STDIO_MAX_EPHEMERAL_SLOTS": "4",
        "BRIDGE_STDIO_MAX_TURN_OUTPUT_BYTES": "8192",
        "BRIDGE_STDIO_HANDSHAKE_TIMEOUT_S": "12.5",
        "BRIDGE_STDIO_TURN_IDLE_TIMEOUT_S": "45.0",
        "BRIDGE_STDIO_TURN_TOTAL_TIMEOUT_S": "120.0",
        "BRIDGE_MUSE_LEAVE_TIMEOUT_S": "3.5",
        "BRIDGE_STDIO_REAP_INTERVAL_S": "7.5",
    })
    assert custom.enabled is True
    assert custom.max_slots == 6
    assert custom.max_slots_per_principal == 3
    assert custom.max_ephemeral_slots == 4
    assert custom.max_turn_output_bytes == 8192
    assert custom.handshake_timeout_s == 12.5
    assert custom.turn_idle_timeout_s == 45.0
    assert custom.turn_total_timeout_s == 120.0
    assert custom.leave_timeout_s == 3.5
    assert custom.reap_interval_s == 7.5

    # max_slots_per_principal is clamped to max_slots
    clamped = StdioPoolConfig.from_env({
        "BRIDGE_STDIO_MAX_SLOTS": "2",
        "BRIDGE_STDIO_MAX_SLOTS_PER_PRINCIPAL": "10",
    })
    assert clamped.max_slots_per_principal == 2

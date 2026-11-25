from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false

import ast
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from adapters.stdio_resident_adapter import StdioResidentAdapter
from core.stdio_resident.config import FLAG_RESIDENT_ENABLED

ROOT = Path(__file__).resolve().parents[1]
FAKE_AGENT = ROOT / "tests" / "stdio_fake_agent.py"
ADAPTER_SOURCE = ROOT / "adapters" / "stdio_resident_adapter.py"


def _config(protocol: str = "stream-json") -> dict[str, Any]:
    return {
        "bridge": {
            "options": {
                "protocol": protocol,
                "cli_argv": [
                    sys.executable,
                    str(FAKE_AGENT),
                    "--protocol",
                    protocol,
                ],
                "output_format_args": [],
            }
        }
    }


def _request(cwd: Path, prompt: str = "hello") -> dict[str, Any]:
    return {
        "chat_key": "chat-1",
        "chat_id": "chat-1",
        "model": "fake-model",
        "effort": "medium",
        "cwd": str(cwd),
        "prompt": prompt,
    }


def test_adapter_preflight_respects_flag(monkeypatch: Any) -> None:
    monkeypatch.delenv(FLAG_RESIDENT_ENABLED, raising=False)
    disabled = StdioResidentAdapter(_config())
    assert disabled.preflight_check() is False
    disabled.shutdown()

    monkeypatch.setenv(FLAG_RESIDENT_ENABLED, "1")
    enabled = StdioResidentAdapter(_config())
    assert enabled.preflight_check() is True
    enabled.shutdown()


def test_adapter_reads_bridge_options_without_backend_adapter_mutation(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv(FLAG_RESIDENT_ENABLED, "1")
    adapter = StdioResidentAdapter(_config("acp"))
    try:
        assert adapter._driver.capabilities.protocol_name == "acp"
    finally:
        adapter.shutdown()


def test_adapter_execute_chat_stream(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv(FLAG_RESIDENT_ENABLED, "1")
    adapter = StdioResidentAdapter(_config())
    try:
        chunks = list(
            adapter.execute_chat(
                _request(tmp_path), trusted_owner_hash="owner-test"
            )
        )
    finally:
        adapter.shutdown()

    assert chunks
    assert all("choices" in chunk for chunk in chunks)
    content = "".join(
        str(chunk["choices"][0]["delta"].get("content", "")) for chunk in chunks
    )
    assert "echo:" in content
    assert "hello" in content
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_adapter_rollback_shutdown(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv(FLAG_RESIDENT_ENABLED, "1")
    adapter = StdioResidentAdapter(_config())
    _ = list(
        adapter.execute_chat(
            _request(tmp_path, "shutdown-check"),
            trusted_owner_hash="owner-test",
        )
    )

    slots = cast(dict[str, Any], vars(adapter._pool)["_slots"])
    handles = [entry.handle for entry in slots.values()]
    assert handles and all(handle.is_alive() for handle in handles)

    adapter.shutdown(timeout_s=1.0)

    assert all(not handle.is_alive() for handle in handles)
    assert not cast(dict[str, Any], vars(adapter._pool)["_slots"])


def test_request_owner_hash_cannot_spoof_pool_identity(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(FLAG_RESIDENT_ENABLED, "1")
    adapter = StdioResidentAdapter(_config())
    trusted_request = _request(tmp_path, "trusted")
    spoofed_request = {**_request(tmp_path, "spoofed"), "owner_hash": "owner-test"}
    seen_ephemeral: list[bool] = []
    orig_acquire = adapter._pool.acquire

    def spy_acquire(*args: Any, **kwargs: Any) -> Any:
        seen_ephemeral.append(bool(kwargs.get("is_ephemeral", False)))
        return orig_acquire(*args, **kwargs)

    monkeypatch.setattr(adapter._pool, "acquire", spy_acquire)
    try:
        _ = list(
            adapter.execute_chat(
                trusted_request,
                trusted_owner_hash="owner-test",
            )
        )
        trusted_slots = cast(dict[str, Any], vars(adapter._pool)["_slots"])
        trusted_entry = next(iter(trusted_slots.values()))
        trusted_pid = trusted_entry.handle.pid
        _ = list(adapter.execute_chat(spoofed_request))
        slots = cast(dict[str, Any], vars(adapter._pool)["_slots"])
        assert seen_ephemeral == [False, True]
        assert len(slots) == 1
        assert next(iter(slots.values())).handle.pid == trusted_pid
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_emulate_tools_writer_suppresses_raw_tool_call_and_enforces_limit() -> None:
    from adapters.stdio_resident_runtime import wrap_emulate_tools_sse_writer
    from core.stdio_resident.resident_runtime import ResourceLimitError

    emitted: list[tuple[str, str]] = []
    closed: list[bool] = []

    def sink(kind: str, value: str) -> bool:
        emitted.append((kind, value))
        return True

    wrapped = wrap_emulate_tools_sse_writer(
        sink,
        True,
        1024,
        lambda: closed.append(True),
    )
    assert wrapped is not None
    assert wrapped("content", "<tool_call>{}</tool_call>") is True
    assert emitted == []
    with pytest.raises(ResourceLimitError, match="output_limit_exceeded"):
        _ = wrapped("reasoning_content", "x" * 1025)
    assert closed == [True]
    assert emitted == []


def test_adapter_zero_vendor_imports() -> None:
    tree = ast.parse(ADAPTER_SOURCE.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)

    assert all(not name.startswith("bridges") for name in modules)
    assert all("agy_runtime" not in name for name in modules)

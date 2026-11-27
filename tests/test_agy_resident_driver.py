"""Тесты резидентного NDJSON-драйвера `agy` (AD-003, VER-004)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from adapters.stdio_drivers.agy_driver import (
    FLAG_AGY_RESIDENT,
    AgyResidentConfig,
    AgyStreamJsonDriver,
    build_agy_pool_config,
    load_agy_resident_config,
)
from core.stdio_resident.process_pool import ResidentProcessPool, _SlotEntry
from core.stdio_resident.types import SlotAffinityKey
from core.timeout_ladder import load_timeout_ladder_config

_WORKER_SRC = r"""
import json, sys
count = 0
for line in sys.stdin:
    if not line.strip():
        continue
    try:
        payload = json.loads(line)
    except ValueError:
        continue
    content = (payload.get("message") or {}).get("content")
    prompt = "".join(str(b.get("text", "")) for b in content if isinstance(b, dict)) if isinstance(content, list) else str(content or "")
    count += 1
    reply = f"echo:{prompt}:{count}"
    delta = {"event": "step_update", "step_update": {"step_type": "agent_response", "text_delta": reply}}
    result = {"event": "result", "result": {"response": reply, "status": "DONE"}}
    sys.stdout.write(json.dumps(delta) + "\n" + json.dumps(result) + "\n"); sys.stdout.flush()
"""


def test_flag_default_disabled_keeps_cold_fallback() -> None:
    assert FLAG_AGY_RESIDENT == "AGY_RESIDENT_ENABLED"
    assert load_agy_resident_config({}).enabled is False
    assert load_agy_resident_config({"AGY_RESIDENT_ENABLED": "false"}).enabled is False
    assert build_agy_pool_config(load_agy_resident_config({})).enabled is False


def test_enabled_config_maps_to_pool_aligned_with_ladder() -> None:
    ladder = load_timeout_ladder_config({"BRIDGE_TIMEOUT_LADDER_ENABLED": "true"})
    assert ladder.effective_idle_s == 600.0
    cfg = load_agy_resident_config(
        {"AGY_RESIDENT_ENABLED": "true"}, ladder_idle_s=ladder.effective_idle_s
    )
    pool_cfg = build_agy_pool_config(cfg)
    assert cfg.enabled is True and pool_cfg.enabled is True
    assert pool_cfg.max_slots == 8
    assert pool_cfg.turn_idle_timeout_s == 600.0 != 180.0
    assert pool_cfg.idle_timeout_s == 600.0 and pool_cfg.ttl_s == 3600.0
    assert pool_cfg.max_rss_bytes == 1024 * 1024 * 1024
    assert pool_cfg.lease_wait_s == 30.0


def test_env_overrides_idle_precedence_and_fail_closed() -> None:
    env = {
        "AGY_RESIDENT_ENABLED": "1",
        "AGY_RESIDENT_MAX_SLOTS": "3",
        "AGY_RESIDENT_IDLE_TIMEOUT_S": "42.5",
        "AGY_RESIDENT_TTL_S": "90",
        "AGY_RESIDENT_MAX_RSS_MB": "256",
        "AGY_RESIDENT_LEASE_WAIT_S": "2.5",
    }
    cfg = load_agy_resident_config(env, ladder_idle_s=600.0)
    assert cfg == AgyResidentConfig(True, 3, 42.5, 90.0, 256, 2.5)
    assert build_agy_pool_config(cfg).max_slots == 3
    assert build_agy_pool_config(cfg).turn_idle_timeout_s == 42.5
    for bad in (
        {"AGY_RESIDENT_ENABLED": "maybe"},
        {"AGY_RESIDENT_MAX_SLOTS": "eight"},
        {"AGY_RESIDENT_IDLE_TIMEOUT_S": "nan"},
        {"AGY_RESIDENT_MAX_SLOTS": "0"},
        {"AGY_RESIDENT_MAX_RSS_MB": "32"},
        {"AGY_RESIDENT_IDLE_TIMEOUT_S": "5000", "AGY_RESIDENT_TTL_S": "60"},
    ):
        with pytest.raises(ValueError):
            _ = load_agy_resident_config(bad)


def test_runtime_registry_blast_radius_and_adapter_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapters.stdio_drivers import infer_protocol
    from adapters.stdio_resident_adapter import StdioResidentAdapter

    bad_off = {"AGY_RESIDENT_MAX_SLOTS": "0", "AGY_RESIDENT_TTL_S": "0"}
    assert infer_protocol("claude", {}, {}, environ=bad_off) == "stream-json"
    assert infer_protocol("agy", {}, {}, environ=bad_off) == "stream-json"
    assert infer_protocol("agy", {}, {}, environ={FLAG_AGY_RESIDENT: "true"}) == "agy-stream-json"
    monkeypatch.setenv(FLAG_AGY_RESIDENT, "true")
    monkeypatch.setenv("AGY_RESIDENT_MAX_SLOTS", "3")
    monkeypatch.setenv("AGY_RESIDENT_IDLE_TIMEOUT_S", "450")
    adapter = StdioResidentAdapter("agy", {})
    assert isinstance(adapter._driver, AgyStreamJsonDriver)
    assert adapter._config.max_slots == 3 and adapter._config.turn_idle_timeout_s == 450.0


def test_config_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        AgyResidentConfig().enabled = True  # type: ignore[misc]


def test_build_argv_adds_stream_json_model_conversation_without_dupes() -> None:
    driver = AgyStreamJsonDriver()
    base = ["agy.real"]
    argv = driver.build_argv(base, {"model": "gemini-x", "conversation_id": "cid-1"})
    assert base == ["agy.real"]
    expected = ["agy.real", "--input-format", "stream-json", "--output-format", "stream-json", "--print-timeout", "30s", "--model", "gemini-x", "--conversation", "cid-1"]
    assert argv == expected
    assert driver.build_argv(argv, {"model": "gemini-x", "conversation_id": "cid-1"}) == argv
    merged = driver.build_argv(["agy.real", "--input-format=stream-json", "--print-timeout=0"], {"print_timeout": 120})
    assert merged.count("--input-format=stream-json") == 1 and "--input-format" not in merged
    assert merged.count("--print-timeout=120s") == 1 and "--print-timeout" not in merged
    assert "--effort" not in driver.build_argv(["agy.real"], {"effort": " off "})


def test_encode_turn_shape_context_and_newline() -> None:
    encoded = AgyStreamJsonDriver().encode_turn("hello", {"session_id": "s-1", "turn_sandbox": "/tmp/x", "cwd": "/tmp"})
    assert encoded.endswith(b"\n")
    payload = json.loads(encoded)
    assert payload["type"] == "user" and payload["event"] == "user"
    assert payload["message"] == {"role": "user", "content": [{"type": "text", "text": "hello"}]}
    assert payload["session_id"] == "s-1"
    assert "turn_sandbox" not in payload and "cwd" not in payload


def test_decode_text_reasoning_and_tool_calls() -> None:
    driver = AgyStreamJsonDriver()
    agy_delta = json.dumps(
        {
            "event": "step_update",
            "step_update": {"step_type": "agent_response", "text_delta": "hi"},
        }
    )
    chunk = driver.decode_line(agy_delta)
    assert chunk is not None and chunk.text == "hi" and not chunk.is_terminal
    generic = driver.decode_line('{"type": "content", "delta": "plain"}')
    assert generic is not None and generic.text == "plain"
    thinking = driver.decode_line('{"type": "thinking", "thinking": "ponder"}')
    assert thinking is not None and thinking.reasoning == "ponder"
    assistant = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "think"},
                    {"type": "text", "text": "say"},
                    {"type": "tool_use", "name": "search", "input": {"q": "x"}},
                ],
            },
        }
    )
    rich = driver.decode_line(assistant)
    assert rich is not None and rich.text == "say" and rich.reasoning == "think"
    assert rich.tool_calls[0]["name"] == "search"
    assert rich.is_tool_stop and driver.is_tool_stop(assistant, rich)
    agy_tool = json.dumps(
        {"event": "step_update", "step_update": {"step_type": "tool", "step_index": 2}}
    )
    tool_chunk = driver.decode_line(agy_tool)
    assert tool_chunk is not None and tool_chunk.is_tool_stop
    assert tool_chunk.tool_calls[0]["step_index"] == 2
    listed = driver.decode_line(
        '{"type": "assistant", "tool_calls": [{"name": "fetch"}]}'
    )
    assert listed is not None and listed.tool_calls == [{"name": "fetch"}]


def test_decode_result_error_and_broken_json() -> None:
    driver = AgyStreamJsonDriver()
    agy_result = json.dumps(
        {"event": "result", "result": {"response": "final", "status": "DONE"}}
    )
    done = driver.decode_line(agy_result)
    assert (
        done is not None
        and done.text == "final"
        and done.is_terminal
        and done.error is None
    )
    assert driver.is_terminal(agy_result, done) and driver.is_terminal(agy_result, None)
    assert driver.is_terminal('{"type": "result", "result": "ok"}', None)
    failed = driver.decode_line(
        '{"event": "result", "result": {"status": "ERROR", "error": "boom"}}'
    )
    assert failed is not None and failed.is_terminal and failed.error == "boom"
    error = driver.decode_line('{"type": "error", "error": {"message": "bad"}}')
    assert error is not None and error.error == "bad" and error.is_terminal
    assert driver.decode_line("{not json") is None and driver.decode_line("") is None
    assert not driver.is_terminal('{"type": "content", "delta": "x"}', None)


def test_fingerprint_stable_and_config_sensitive() -> None:
    first = AgyStreamJsonDriver().compute_fingerprint()
    assert first == AgyStreamJsonDriver().compute_fingerprint() and len(first) == 64
    assert (
        AgyStreamJsonDriver(AgyResidentConfig(max_slots=2)).compute_fingerprint()
        != first
    )
    assert AgyStreamJsonDriver().capabilities.protocol_name == "agy-stream-json"


def _affinity(cid: str, cwd: str) -> SlotAffinityKey:
    return SlotAffinityKey(
        owner_hash="owner-agy-test",
        chat_key=cid,
        backend_id="agy",
        model="test-model",
        effort="",
        cwd_norm=cwd, env_digest="",
    )


def _run_turn(
    pool: ResidentProcessPool,
    driver: AgyStreamJsonDriver,
    key: SlotAffinityKey,
    builder: Callable[[], list[str]],
    prompt: str,
) -> tuple[int, str, _SlotEntry]:
    entry = pool.acquire(key, builder, key.cwd_norm)
    try:
        entry.handle.write(driver.encode_turn(prompt))
        texts: list[str] = []
        while True:
            tagged = entry.handle.read_line(timeout_s=10.0)
            assert tagged is not None, "echo worker closed the turn without result"
            if tagged.is_stderr:
                continue
            decoded = driver.decode_line(tagged.line)
            if decoded is not None:
                assert decoded.error is None
                texts.append(decoded.text)
            if driver.is_terminal(tagged.line, decoded):
                break
        return entry.handle.pid, "".join(texts), entry
    finally:
        pool.release(entry.slot_id, lease_id=entry.lease_id)


def test_live_pool_reuses_pid_per_conversation(tmp_path: Path) -> None:
    worker = tmp_path / "echo_worker.py"
    _ = worker.write_text(_WORKER_SRC, encoding="utf-8")
    cfg = AgyResidentConfig(
        enabled=True, idle_timeout_s=30.0, ttl_s=120.0, lease_wait_timeout_s=5.0
    )
    driver = AgyStreamJsonDriver(cfg)
    pool = ResidentProcessPool(
        replace(build_agy_pool_config(cfg), cancel_grace_s=0.5, shutdown_timeout_s=2.0)
    )
    cwd = str(tmp_path)
    handles: dict[int, Any] = {}

    def builder_for(cid: str) -> Callable[[], list[str]]:
        return lambda: driver.build_argv(
            [sys.executable, str(worker)],
            {"model": "test-model", "conversation_id": cid},
        )

    try:
        pid1, text1, entry1 = _run_turn(
            pool, driver, _affinity("cid-A", cwd), builder_for("cid-A"), "hello"
        )
        pid2, text2, entry2 = _run_turn(
            pool, driver, _affinity("cid-A", cwd), builder_for("cid-A"), "again"
        )
        pid3, text3, entry3 = _run_turn(
            pool, driver, _affinity("cid-B", cwd), builder_for("cid-B"), "hello"
        )
        handles = {e.handle.pid: e.handle for e in (entry1, entry2, entry3)}
        assert pid1 > 0 and pid2 == pid1
        assert "echo:hello:1" in text1 and "echo:again:2" in text2
        assert pid3 != pid1
        assert "echo:hello:1" in text3 and "again" not in text3
    finally:
        # Реальный API пула — `shutdown()`; имя из брифа пробуется как алиас.
        shutdown_all = getattr(pool, "shutdown_all", None)
        if callable(shutdown_all):
            shutdown_all()
        else:
            pool.shutdown(timeout_s=2.0)
    assert handles and all(not handle.is_alive() for handle in handles.values())

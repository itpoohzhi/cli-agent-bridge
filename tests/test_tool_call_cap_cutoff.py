"""L1/L2: graceful cap-cutoff на 64 вызовах, parallel-срез, bytes-лимит и kill-switch флаги."""

from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core import recovery_flags as rf  # noqa: E402
from core.log_redaction import redact_log_text  # noqa: E402
from core.tool_call_cap_policy import evaluate_bytes_cap, evaluate_call_cap  # noqa: E402
from core.tool_call_schema_policy import ToolCallLimitExceededError  # noqa: E402
from core.tool_turn_settle_policy import decide_session_commit  # noqa: E402
_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}, "description": {"type": "string"}},
                "required": ["command", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    },
]


def _load_agy_bridge() -> Any:
    name = "agy_bridge_server_cap_cutoff_test"
    if name in sys.modules:
        return sys.modules[name]
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-cap-cutoff")
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / "bridges/agy-bridge/server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _iter_chunks(text: str, mode: str) -> list[str]:
    if mode == "whole":
        return [text]
    if mode == "seeded":
        rng = random.Random(42)
        out: list[str] = []
        i = 0
        while i < len(text):
            step = rng.randint(1, 29)
            out.append(text[i : i + step])
            i += step
        return out
    step = int(mode)
    return [text[i : i + step] for i in range(0, len(text), step)]


def _make_burst_payload(count: int) -> str:
    blocks = [
        (
            '<tool_call>{"name":"read","arguments":{"path":"f.txt"}}</tool_call>'
            if i == count - 1
            else f'<tool_call>{{"name":"bash","arguments":{{"command":"echo {i}","description":"s{i}"}}}}</tool_call>'
        )
        for i in range(count)
    ]
    return "\n".join(blocks) + "\n<tool_"


def _isolate_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, cap_cutoff: bool) -> None:
    monkeypatch.setenv(rf.CONFIG_PATH_ENV, str(tmp_path / "missing.json"))
    monkeypatch.delenv("AGY_MAX_TOOL_CALLS", raising=False)
    monkeypatch.delenv("AGY_MAX_TOOL_BYTES", raising=False)
    if cap_cutoff:
        monkeypatch.setenv(rf.TOOL_CALL_CAP_CUTOFF_FLAG_ENV, "1")
    else:
        monkeypatch.delenv(rf.TOOL_CALL_CAP_CUTOFF_FLAG_ENV, raising=False)


@pytest.mark.parametrize("total_calls", [65, 66])
@pytest.mark.parametrize("mode", ["whole", "1", "7", "17", "seeded"])
def test_cap_cutoff_delivers_64_invalidates_cid_and_is_chunk_invariant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, total_calls: int, mode: str
) -> None:
    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=True)
    srv = _load_agy_bridge()
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", lambda msg, *_a, **_kw: logs.append(str(msg)))
    emitted: list[dict[str, Any]] = []
    turn = srv._ToolTurn(_TOOLS, lambda _c: True, lambda _r: True, lambda b: emitted.extend(b) or True)
    payload = _make_burst_payload(total_calls)
    for chunk in _iter_chunks(payload, mode):
        assert turn.feed(chunk) is True
    turn.finish()

    assert turn.error == ""
    assert len(turn.calls) == 64 and len(emitted) == 64
    assert [int(c["index"]) for c in emitted] == list(range(64))
    settle = turn.settle_decision()
    assert settle.action == "forced_stop" and settle.should_stop is True
    assert settle.tool_turn_stop is True and settle.tool_turn_clean_eof is False
    assert decide_session_commit(
        state="done", rc=0, tool_turn_stop=settle.tool_turn_stop, conversation_id="cid-hot", cid_valid=True
    ) == "invalidate"
    cutoff_logs = [ln for ln in logs if "tool_call_cap_cutoff" in ln]
    assert len(cutoff_logs) == 1
    assert redact_log_text(cutoff_logs[0]) == cutoff_logs[0]


def test_cap_cutoff_parallel_batch_slices_to_exact_64(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=True)
    srv = _load_agy_bridge()
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", lambda msg, *_a, **_kw: logs.append(str(msg)))
    emitted: list[dict[str, Any]] = []
    turn = srv._ToolTurn(_TOOLS, lambda _c: True, lambda _r: True, lambda b: emitted.extend(b) or True)
    prefix = "\n".join(
        f'<tool_call>{{"name":"bash","arguments":{{"command":"echo {i}","description":"d{i}"}}}}</tool_call>'
        for i in range(62)
    )
    subcalls = [{"name": "bash", "arguments": {"command": f"p{i}", "description": f"pd{i}"}} for i in range(5)]
    parallel_block = "<tool_call>" + json.dumps({"name": "parallel", "arguments": {"tool_uses": subcalls}}) + "</tool_call>"
    turn.feed(prefix + "\n" + parallel_block)
    turn.finish()

    assert turn.error == ""
    assert len(turn.calls) == 64 and len(emitted) == 64
    assert [int(c["index"]) for c in emitted[-2:]] == [62, 63]
    assert any("tool_call_cap_cutoff kind=calls accepted=64 observed=67 limit=64" in ln for ln in logs)


def test_cap_cutoff_disabled_default_keeps_legacy_limit_error_and_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=False)
    srv = _load_agy_bridge()
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", lambda msg, *_a, **_kw: logs.append(str(msg)))
    turn = srv._ToolTurn(_TOOLS, lambda _c: True, lambda _r: True, lambda _b: True)
    turn.feed(_make_burst_payload(65))
    turn.finish()

    assert turn.error != ""
    assert isinstance(turn._limit_error, ToolCallLimitExceededError)
    assert (turn._limit_error.limit_kind, turn._limit_error.observed, turn._limit_error.limit) == ("calls", 65, 64)
    assert turn.error_body()["type"] == "tool_call_limit_exceeded"
    limit_logs = [ln for ln in logs if "tool_call_limit exceeded" in ln]
    assert len(limit_logs) == 1
    assert redact_log_text(limit_logs[0]) == limit_logs[0]


def test_bytes_limit_classification_under_flag_and_legacy_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_agy_bridge()
    dec = evaluate_bytes_cap(current_bytes=60, chunk_bytes=40, max_bytes=80)
    assert dec.action == "limit_error" and dec.limit_kind == "bytes"
    assert redact_log_text(dec.log_line) == dec.log_line
    assert evaluate_call_cap(current_calls=62, incoming_calls=5, max_calls=64, cap_cutoff_enabled=True).accept_count == 2

    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=True)
    monkeypatch.setenv("AGY_MAX_TOOL_BYTES", "80")
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", lambda msg, *_a, **_kw: logs.append(str(msg)))
    turn = srv._ToolTurn(_TOOLS, lambda _c: True, lambda _r: True, lambda _b: True)
    turn.feed("я" * 50)
    assert isinstance(turn._limit_error, ToolCallLimitExceededError)
    assert turn._limit_error.limit_kind == "bytes"
    body = turn.error_body()
    assert body["type"] == "tool_call_limit_exceeded"
    assert "malformed" not in str(body["message"]).lower()
    assert "tool call buffer exceeded max bytes" in str(body["detail"])
    assert any("tool_call_limit exceeded kind=bytes" in ln for ln in logs)

    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=False)
    monkeypatch.setenv("AGY_MAX_TOOL_BYTES", "80")
    logs_legacy: list[str] = []
    monkeypatch.setattr(srv, "_log", lambda msg, *_a, **_kw: logs_legacy.append(str(msg)))
    turn_legacy = srv._ToolTurn(_TOOLS, lambda _c: True, lambda _r: True, lambda _b: True)
    turn_legacy.feed("я" * 50)
    assert isinstance(turn_legacy._limit_error, ToolCallLimitExceededError)
    assert turn_legacy._limit_error.limit_kind == "bytes"
    assert turn_legacy.error_body()["type"] == "tool_call_limit_exceeded"
    assert "tool call buffer exceeded max bytes" in turn_legacy.error
    assert any("tool_call_limit exceeded kind=bytes" in ln for ln in logs_legacy)


@pytest.mark.parametrize(
    ("env_name", "reader"),
    [
        (rf.TOOL_JSON_REPAIR_FLAG_ENV, rf.read_tool_json_repair_enabled),
        (rf.TOOL_CALL_CAP_CUTOFF_FLAG_ENV, rf.read_tool_call_cap_cutoff_enabled),
    ],
)
def test_new_recovery_kill_switch_flags_fail_closed(
    tmp_path: Path, env_name: str, reader: Any
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    assert reader({}, cfg) is False
    assert reader({env_name: "1"}, cfg) is True
    _ = cfg.write_text(json.dumps({env_name: True}), encoding="utf-8")
    assert reader({}, cfg) is True
    assert reader({env_name: "0"}, cfg) is False
    _ = cfg.write_text(json.dumps({env_name: False}), encoding="utf-8")
    assert reader({env_name: "1"}, cfg) is False
    _ = cfg.write_text("{broken json", encoding="utf-8")
    assert reader({env_name: "1"}, cfg) is False
    link = tmp_path / "link.json"
    real = tmp_path / "real.json"
    _ = real.write_text(json.dumps({env_name: True}), encoding="utf-8")
    link.symlink_to(real)
    assert reader({env_name: "1"}, link) is False


@pytest.mark.parametrize("limit", [0, -1])
@pytest.mark.parametrize("cap_cutoff", [False, True])
def test_zero_and_negative_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, limit: int, cap_cutoff: bool
) -> None:
    d_calls = evaluate_call_cap(current_calls=0, incoming_calls=1, max_calls=limit, cap_cutoff_enabled=cap_cutoff)
    assert d_calls.action == "limit_error" and d_calls.accept_count == 0
    d_bytes = evaluate_bytes_cap(current_bytes=0, chunk_bytes=1, max_bytes=limit)
    assert d_bytes.action == "limit_error" and d_bytes.accept_count == 0

    srv = _load_agy_bridge()
    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=cap_cutoff)
    emitted: list[dict[str, object]] = []
    turn = srv._ToolTurn(_TOOLS, lambda cs: emitted.extend(cs) or True, lambda _r: True, lambda _b: True)
    turn._max_calls = limit
    turn.feed('<tool_call>{"name":"bash","arguments":{"command":"echo blocked"}}</tool_call>')
    turn.finish()
    assert emitted == [] and turn.calls == [] and turn.error
    assert turn._cap_cutoff is False

    turn_b = srv._ToolTurn(_TOOLS, lambda _c: True, lambda _r: True, lambda _b: True)
    turn_b._max_bytes = limit
    turn_b.feed("x")
    assert turn_b.error and "max bytes" in turn_b.error


def test_cap_cutoff_suppresses_malformed_tail_atomically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_agy_bridge()
    _isolate_flags(monkeypatch, tmp_path, cap_cutoff=True)
    monkeypatch.setenv("BRIDGE_TOOL_JSON_REPAIR_ENABLED", "1")
    monkeypatch.setenv("AGY_MAX_TOOL_CALLS", "2")
    bad_tail = 'TRAILING_TEXT<tool_call>{"name":"bash","arguments":{"command":"broken'
    normal_chunk = (
        '<tool_call>{"name":"bash","arguments":{"command":"echo 1"}}</tool_call>'
        '<tool_call>{"name":"bash","arguments":{"command":"echo 2"}}</tool_call>'
        '<tool_call>{"name":"bash","arguments":{"command":"echo 3"}}</tool_call>'
        + bad_tail
    )
    emitted: list[dict[str, object]] = []
    texts: list[str] = []
    turn = srv._ToolTurn(_TOOLS, lambda t: texts.append(t) or True, lambda r: texts.append(r) or True, lambda cs: emitted.extend(cs) or True)
    turn.feed(normal_chunk)
    turn.finish()
    assert turn.error == "" and turn._cap_cutoff is True and len(turn.calls) == 2 and len(emitted) == 2
    assert turn._normalizer.has_open_tool_call() is False and "TRAILING_TEXT" not in "".join(texts)

    from core.tool_emulation import ToolCallParser
    odd_block = '<tool_call>{"name":"bash","arguments":{"command":"echo "hi"}}</tool_call>'
    p_calls: list[dict[str, object]] = []
    p_text: list[str] = []
    parser = ToolCallParser(p_text.append, lambda c: (p_calls.append(c), parser.suppress_tail())[0], strict_live=True)
    parser.configure_json_repair(True)
    parser.feed(odd_block + bad_tail)
    parser.finish()
    assert len(p_calls) == 1 and parser.has_open_tool_call() is False and "TRAILING_TEXT" not in "".join(p_text)

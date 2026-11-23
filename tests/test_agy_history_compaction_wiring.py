"""W3: adversarial QA и телеметрия wiring компакции истории (VER-004/008).

Структурированный лог адаптера (mode/prompt_bytes/limit/prompt_prefix_sha256/
digested/dropped) без утечки текста истории, fallback на legacy при ошибке
домена и превышении input guard, краевые истории через
``server._messages_to_prompt`` и флаг AD-005 (кодовый дефолт, dynamic_config,
приоритет env).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

import agy_runtime.history_compaction_adapter as _adapter  # noqa: E402
from agy_runtime.history_compaction_adapter import (  # noqa: E402
    CompactionAdapterRequest,
    render_or_compact_blocks,
)

_CANARY = "CANARY_FACT_ALPHA_7391"
_CODENAME = "LARCH-7391"
_SECRET = "SECRET_FRAGMENT_9911"
_LIMIT = 98304
_FLAG_ENV = "AGY_HISTORY_COMPACTION_ENABLED"
_GUARD_ENV = "AGY_HISTORY_COMPACTION_INPUT_GUARD_BYTES"
_LINE_RE = re.compile(
    r"mode=(?P<mode>\w+) prompt_bytes=(?P<bytes>\d+) limit=(?P<limit>\d+) "
    r"prompt_prefix_sha256=(?P<sha>[0-9a-f]{64}) digested=(?P<dig>\d+) "
    r"dropped=(?P<drop>\d+)"
)


def _load_srv() -> ModuleType:
    cached = sys.modules.get("agy_srv_wiring_w3")
    if cached is not None:
        return cached
    srv_path = _ROOT / "bridges/agy-bridge/server.py"
    spec = importlib.util.spec_from_file_location("agy_srv_wiring_w3", srv_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod.__name__] = mod
    spec.loader.exec_module(mod)
    return mod


srv = _load_srv()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    cfg = tmp_path / "dynamic_config.json"
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES", str(_LIMIT))
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES_CAP", str(_LIMIT))
    monkeypatch.setenv("AGY_TRUNCATION_NOTICE_ENABLED", "false")
    monkeypatch.delenv(_FLAG_ENV, raising=False)
    monkeypatch.delenv(_GUARD_ENV, raising=False)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setattr(srv, "AGY_BRIDGE_ENABLE_HEAD_PRUNING", True)
    monkeypatch.setattr(srv, "_cfg_snapshot", srv._COLD_FLAGS)
    monkeypatch.setattr(srv, "_cfg_key", None)
    monkeypatch.setattr(srv, "_cfg_checked_at", None)
    yield cfg


def _write_cfg(cfg: Path, **flags: bool) -> None:
    cfg.write_text(json.dumps(flags), encoding="utf-8")
    srv._cfg_checked_at = None
    srv._cfg_key = None


def _block(idx: int, role: str, body: str) -> tuple[int, str, str]:
    return (idx, role, f"### {idx}. {role}\n{body}")


def _blocks(turns: int, secret: str = "") -> list[tuple[int, str, str]]:
    blocks = [
        _block(0, "system", "You are a test assistant. Follow the conversation."),
        _block(1, "user", f"Remember this fact: {_CANARY} codename is {_CODENAME}."),
    ]
    for turn in range(turns):
        cid, base = "call_%02d" % turn, 2 + turn * 3
        blocks.append(_block(base, "user", f"step {turn}: read chunk {turn}"))
        text = f"[tool call {cid}] read_chunk({turn})"
        blocks.append(_block(base + 1, "assistant", text))
        body = f"[tool result {cid}] {secret} result-{turn:02d}-" + "x" * 4200
        blocks.append(_block(base + 2, "tool", body))
    blocks.append(_block(2 + turns * 3, "user", "What is the codename?"))
    return blocks


def _render(
    blocks: list[tuple[int, str, str]], enabled: bool, logs: list[str], cfg: Path
) -> str:
    req = CompactionAdapterRequest(
        blocks=blocks,
        tail_block="",
        limit_bytes=_LIMIT,
        enabled=enabled,
        legacy_prune=srv._prune_prompt_blocks,
        log_fn=logs.append,
        config_path=cfg,
        size_fn=srv._ndjson_bytes,
    )
    return render_or_compact_blocks(req)


def _legacy(blocks: list[tuple[int, str, str]]) -> str:
    return srv._prune_prompt_blocks(blocks, "", _LIMIT)


def _telemetry(logs: list[str], mode: str) -> re.Match[str]:
    for line in logs:
        match = _LINE_RE.search(line)
        if match and match.group("mode") == mode and "history compaction:" in line:
            return match
    raise AssertionError(f"no telemetry line mode={mode} in {logs!r}")


def _assert_no_leak(logs: list[str]) -> None:
    joined = "\n".join(logs)
    for forbidden in (_CANARY, _CODENAME, _SECRET, "Remember this fact", "step 0"):
        assert forbidden not in joined, f"log leaked history text: {forbidden}"


def _assert_fields(logs: list[str], mode: str) -> re.Match[str]:
    match = _telemetry(logs, mode)
    assert int(match.group("limit")) == _LIMIT
    assert int(match.group("bytes")) <= _LIMIT
    assert re.fullmatch(r"[0-9a-f]{64}", match.group("sha"))
    _assert_no_leak(logs)
    return match


def test_telemetry_legacy_mode_log_fields_and_no_leak(_isolate: Path) -> None:
    logs: list[str] = []
    prompt = _render(_blocks(32, _SECRET), False, logs, _isolate)
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    assert prompt == _legacy(_blocks(32, _SECRET))
    match = _assert_fields(logs, "legacy")
    assert int(match.group("dig")) == 0


def test_telemetry_compact_mode_log_fields_and_no_leak(_isolate: Path) -> None:
    logs: list[str] = []
    prompt = _render(_blocks(32, _SECRET), True, logs, _isolate)
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    assert _CANARY in prompt and _CODENAME in prompt
    match = _assert_fields(logs, "compact")
    assert int(match.group("dig")) > 0


def test_telemetry_fallback_mode_on_compact_error(
    _isolate: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object) -> None:
        raise RuntimeError(f"domain exploded {_SECRET}")

    monkeypatch.setattr(_adapter, "compact_prompt_blocks", _boom)
    logs: list[str] = []
    prompt = _render(_blocks(32, _SECRET), True, logs, _isolate)
    assert prompt == _legacy(_blocks(32, _SECRET))
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    _assert_fields(logs, "fallback")
    assert "reason=compact_error" in "\n".join(logs)


def test_telemetry_prefix_sha256_stable_as_history_grows(_isolate: Path) -> None:
    logs_a: list[str] = []
    logs_b: list[str] = []
    _render(_blocks(30), True, logs_a, _isolate)
    _render(_blocks(35), True, logs_b, _isolate)
    sha_a = _telemetry(logs_a, "compact").group("sha")
    sha_b = _telemetry(logs_b, "compact").group("sha")
    assert sha_a == sha_b, "anchor prefix hash drifted as history grew"
    _assert_no_leak(logs_a + logs_b)


def test_telemetry_no_leak_across_modes(
    _isolate: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs: list[str] = []
    _render(_blocks(32, _SECRET), False, logs, _isolate)
    _render(_blocks(32, _SECRET), True, logs, _isolate)
    monkeypatch.setenv(_GUARD_ENV, "1024")
    _render(_blocks(32, _SECRET), True, logs, _isolate)
    for mode in ("legacy", "compact", "fallback"):
        _assert_fields(logs, mode)


def test_fallback_on_input_guard_exceeded_via_env(
    _isolate: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_GUARD_ENV, "1024")
    logs: list[str] = []
    prompt = _render(_blocks(32, _SECRET), True, logs, _isolate)
    assert prompt == _legacy(_blocks(32, _SECRET))
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    _assert_fields(logs, "fallback")
    assert "reason=input_guard" in "\n".join(logs)


def _srv_messages(turns: int) -> list[dict[str, object]]:
    msgs: list[dict[str, object]] = [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": f"Remember: {_CANARY} codename is {_CODENAME}."},
    ]
    for turn in range(turns):
        cid = "call_%02d" % turn
        msgs.append({"role": "user", "content": f"step {turn}: read chunk {turn}"})
        call = {
            "id": cid,
            "type": "function",
            "function": {"name": "read_chunk", "arguments": "{}"},
        }
        msgs.append({"role": "assistant", "content": "", "tool_calls": [call]})
        body = f"result-{turn:02d}-" + "x" * 4200
        msgs.append({"role": "tool", "tool_call_id": cid, "content": body})
    msgs.append({"role": "user", "content": "What is the codename?"})
    return msgs


def _prompt(monkeypatch: pytest.MonkeyPatch, msgs: list[dict[str, object]]) -> str:
    monkeypatch.setenv(_FLAG_ENV, "true")
    return srv._messages_to_prompt(msgs)


def test_edge_empty_and_single_short(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _prompt(monkeypatch, []) == "Reply with exactly: PONG"
    prompt = _prompt(monkeypatch, [{"role": "user", "content": "hello short"}])
    assert "hello short" in prompt
    assert srv._ndjson_bytes(prompt) <= _LIMIT


def test_edge_single_giant_block(monkeypatch: pytest.MonkeyPatch) -> None:
    msgs = [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "HUGE-HEAD " + "a" * 150000 + " HUGE-TAIL"},
    ]
    prompt = _prompt(monkeypatch, msgs)
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    assert "HUGE-HEAD" in prompt and "HUGE-TAIL" in prompt


def test_edge_only_tool_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    msgs: list[dict[str, object]] = []
    for i in range(20):
        content = f"payload-{i} " + "z" * 8000
        msg = {"role": "tool", "tool_call_id": f"call_x{i}", "content": content}
        msgs.append(msg)
    prompt = _prompt(monkeypatch, msgs)
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    assert "call_x19" in prompt


def test_edge_cold_replay_35_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt = _prompt(monkeypatch, _srv_messages(35))
    assert srv._ndjson_bytes(prompt) <= _LIMIT
    assert _CANARY in prompt and _CODENAME in prompt
    assert "What is the codename?" in prompt


def test_flag_code_default_is_false() -> None:
    assert srv._RuntimeFlags().history_compaction_enabled is False
    assert srv._COLD_FLAGS.history_compaction_enabled is False


def test_flag_dynamic_config_toggle(_isolate: Path) -> None:
    assert srv._new_flag("history_compaction_enabled") is False
    _write_cfg(_isolate, history_compaction_enabled=True)
    assert srv._new_flag("history_compaction_enabled") is True
    _write_cfg(_isolate, history_compaction_enabled=False)
    assert srv._new_flag("history_compaction_enabled") is False


def test_flag_env_overrides_dynamic_config(
    _isolate: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_cfg(_isolate, history_compaction_enabled=True)
    monkeypatch.setenv(_FLAG_ENV, "false")
    assert srv._new_flag("history_compaction_enabled") is False
    _write_cfg(_isolate, history_compaction_enabled=False)
    monkeypatch.setenv(_FLAG_ENV, "true")
    assert srv._new_flag("history_compaction_enabled") is True

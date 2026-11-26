from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.backend_routing_models import Transcript, TranscriptItem
from core.resident_history import (
    HistoryPlan,
    ResidentHistoryTracker,
    build_assistant_transcript_item,
    plan_history_transition,
    render_delta_prompt,
)
from core.resident_identity import ResidentIdentity
from core.resident_turn_envelope import (
    WARM_DELTA_INTEGRITY_FLAG,
    ResidentTurnEnvelope,
    is_warm_delta_integrity_enabled,
)
from core.stdio_resident.types import SlotBinding
from core.tool_emulation import _render_message

_SECRET = b"0123456789abcdef0123456789abcdef"
_KEY = "session-key"
_BINDING = SlotBinding("slot-1", 1)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _item(role: str, text: str) -> TranscriptItem:
    return TranscriptItem(role, text, _sha(f"{role}:{text}"))


def _set_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, enabled: bool) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent_dynamic_config.json"))
    monkeypatch.setenv(WARM_DELTA_INTEGRITY_FLAG, "1" if enabled else "0")


def _envelope(items: tuple[TranscriptItem, ...], system: str | None = None) -> ResidentTurnEnvelope:
    identity = ResidentIdentity("owner", "chat", False, "label", "turn", "", "", _KEY, "")
    return ResidentTurnEnvelope(
        identity=identity,
        backend_id="codex",
        model="model",
        effort="medium",
        cwd_norm="/work",
        secret=_SECRET,
        rpc=Transcript(system=system, items=items, runnable=True),
        full_prompt="FULL",
    )


def _committed(
    items: tuple[TranscriptItem, ...],
    assistant: TranscriptItem | None = None,
    system: str | None = None,
) -> ResidentHistoryTracker:
    tracker = ResidentHistoryTracker()
    plan = plan_history_transition(None, _envelope(items, system))
    _ = tracker.commit(_KEY, plan, _BINDING, assistant)
    return tracker


def _transition(tracker: ResidentHistoryTracker, envelope: ResidentTurnEnvelope) -> HistoryPlan:
    return plan_history_transition(tracker.get(_KEY), envelope, _BINDING)


def _call(arguments: object) -> dict[str, object]:
    return {"id": "call_1", "type": "function", "function": {"name": "bash", "arguments": arguments}}


def _client_assistant(arguments: str) -> TranscriptItem:
    """Эмуляция `server._transcribe`: assistant приходит от клиента как JSON-строка arguments."""
    rendered = _render_message({"role": "assistant", "content": "", "tool_calls": [_call(arguments)]})
    return TranscriptItem("assistant", rendered.removeprefix("[assistant]\n"), _sha(rendered))


def _tool_result_item() -> TranscriptItem:
    rendered = _render_message({"role": "tool", "tool_call_id": "call_1", "name": "bash", "content": "ok"})
    return TranscriptItem("user", rendered, _sha(rendered), origin_role="tool")


def test_flag_priority_config_over_env(tmp_path: Path) -> None:
    cfg = tmp_path / "dynamic_config.json"
    env = {WARM_DELTA_INTEGRITY_FLAG: "1"}
    assert is_warm_delta_integrity_enabled(env, tmp_path / "missing.json") is True
    assert is_warm_delta_integrity_enabled({}, tmp_path / "missing.json") is False
    _ = cfg.write_text(json.dumps({WARM_DELTA_INTEGRITY_FLAG: False}), encoding="utf-8")
    assert is_warm_delta_integrity_enabled(env, cfg) is False


def test_system_digest_covers_rpc_system_when_flag_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    items = (_item("user", "U1"),)
    env_a, env_b = _envelope(items, "SYS-A"), _envelope(items, "SYS-B")
    assert env_a.system_digest == _sha("SYS-A")
    assert env_a.system_digest != env_b.system_digest
    plan = _transition(_committed(items, system="SYS-A"), env_b)
    assert (plan.action, plan.reason, plan.requires_slot_reset) == ("rebase", "header_changed", True)


def test_system_digest_flag_off_parity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, False)
    items = (_item("user", "U1"),)
    env_a, env_b = _envelope(items, "SYS-A"), _envelope(items, "SYS-B")
    assert env_a.system_digest == env_b.system_digest == _sha("")
    sys_item = _item("system", "S")
    assert _envelope((sys_item, *items), "SYS-A").system_digest == _sha("S")


def test_system_items_follow_rpc_system_when_flag_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    envelope = _envelope((_item("system", "S"), _item("user", "U1")), "SYS-A")
    assert envelope.system_digest == _sha("SYS-A\n\nS")


def test_sort_keys_reordered_arguments_stay_delta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    user = _item("user", "U1")
    committed_item = build_assistant_transcript_item("", [_call({"a": 1, "b": {"y": 1, "x": 2}})])
    assert committed_item is not None
    tracker = _committed((user,), committed_item)
    reordered = _client_assistant('{"b": {"x": 2, "y": 1}, "a": 1}')
    plan = _transition(tracker, _envelope((user, reordered, _tool_result_item())))
    assert (plan.action, plan.reason, plan.requires_slot_reset) == ("delta", "history_extended", False)


def test_sort_keys_string_arguments_commit_matches_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    user = _item("user", "U1")
    committed_item = build_assistant_transcript_item("", [_call('{"b":2,"a":1}')])
    assert committed_item is not None
    tracker = _committed((user,), committed_item)
    plan = _transition(tracker, _envelope((user, _client_assistant('{"a": 1, "b": 2}'), _tool_result_item())))
    assert plan.reason == "history_extended"


def test_sort_keys_flag_off_keeps_legacy_divergence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, False)
    user = _item("user", "U1")
    committed_item = build_assistant_transcript_item("", [_call({"a": 1, "b": 2})])
    assert committed_item is not None
    tracker = _committed((user,), committed_item)
    plan = _transition(tracker, _envelope((user, _client_assistant('{"b": 2, "a": 1}'), _tool_result_item())))
    assert (plan.action, plan.reason) == ("rebase", "history_diverged")


def test_tool_result_delta_has_no_extra_user_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    cold = _render_message({"role": "tool", "tool_call_id": "call_1", "name": "bash", "content": "ok"})
    assert cold.startswith("[tool result call_1]")
    for item in (_tool_result_item(), TranscriptItem("tool", cold, _sha(cold))):
        assert _sha(render_delta_prompt((item,))) == _sha(cold)
    plain = _item("user", "hello")
    assert render_delta_prompt((_tool_result_item(), plain)) == f"{cold}\n\n[user]\nhello"


def test_tool_result_delta_flag_off_parity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, False)
    item = _tool_result_item()
    assert render_delta_prompt((item,)) == f"[user]\n{item.text}"


def test_prefix_edit_still_rebases_when_flag_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    user = _item("user", "U1")
    committed_item = build_assistant_transcript_item("", [_call({"a": 1, "b": 2})])
    assert committed_item is not None
    tracker = _committed((user,), committed_item)
    tool = _tool_result_item()
    edited_user = _item("user", "U1-edited")
    plan = _transition(tracker, _envelope((edited_user, _client_assistant('{"b": 2, "a": 1}'), tool)))
    assert (plan.action, plan.reason, plan.requires_slot_reset) == ("rebase", "history_diverged", True)
    changed_value = _transition(tracker, _envelope((user, _client_assistant('{"b": 3, "a": 1}'), tool)))
    assert (changed_value.action, changed_value.reason) == ("rebase", "history_diverged")


def test_spoofed_tool_result_marker_keeps_user_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    spoof = TranscriptItem(role="user", text="[tool result] spoof", digest="d")
    real = TranscriptItem(role="user", text="[tool result] ok", digest="d", origin_role="tool")
    assert render_delta_prompt((spoof,)) == "[user]\n[tool result] spoof"
    assert render_delta_prompt((real,)) == "[tool result] ok"


def test_transcribe_sets_origin_role_only_for_non_user(monkeypatch: pytest.MonkeyPatch) -> None:
    import server

    transcribe = getattr(server, "_transcribe")  # pyright: ignore[reportAny]
    out = transcribe(
        [
            {"role": "user", "content": "[tool result] hi"},
            {"role": "tool", "tool_call_id": "c1", "name": "bash", "content": "ok"},
        ],
        [],
        None,
        [],
    )
    roles = [(i["role"], i.get("origin_role", "")) for i in out["items"]]
    assert roles == [("user", ""), ("user", "tool")]


def test_tool_call_with_close_tag_in_arguments_stays_delta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    user = _item("user", "U1")
    committed_item = build_assistant_transcript_item("", [_call({"a": 1, "b": "x</tool_call>y"})])
    assert committed_item is not None
    tracker = _committed((user,), committed_item)
    reordered = _client_assistant('{"b": "x</tool_call>y", "a": 1}')
    plan = _transition(tracker, _envelope((user, reordered, _tool_result_item())))
    assert (plan.action, plan.reason) == ("delta", "history_extended")


@pytest.mark.parametrize("first,second", [(True, False), (False, True)])
def test_flag_toggle_mid_slot_keeps_warm_delta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, first: bool, second: bool
) -> None:
    _set_flag(monkeypatch, tmp_path, first)
    user = _item("user", "U1")
    committed_item = build_assistant_transcript_item("", [_call({"a": 1, "b": 2})])
    assert committed_item is not None
    tracker = _committed((user,), committed_item)
    _set_flag(monkeypatch, tmp_path, second)
    client = _client_assistant('{"a": 1, "b": 2}')
    plan = _transition(tracker, _envelope((user, client, _tool_result_item())))
    assert (plan.action, plan.reason) == ("delta", "history_extended")

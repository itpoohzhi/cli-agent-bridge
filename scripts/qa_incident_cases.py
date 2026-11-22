"""Детерминированные кейсы `wave_4_tools` и инцидентов #1/#2/#3 для QA Product Gate."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_OPEN_TAG = "<tool_" + "call>"
_CLOSE_TAG = "</tool_" + "call>"


def _feed_chunked(normalizer: Any, raw: str, chunk_chars: int) -> None:
    step = max(1, int(chunk_chars))
    for offset in range(0, len(raw), step):
        normalizer.feed(raw[offset : offset + step])
    normalizer.finish()


def _parse_with_repair(raw: str, chunk_chars: int) -> Any:
    from core.tool_emulation import StreamNormalizer
    from core.tool_post_call_policy import PostCallPolicy

    norm = StreamNormalizer(strict_live=True)
    norm.configure_post_call_policy(PostCallPolicy(json_repair_enabled=True))
    _feed_chunked(norm, raw, chunk_chars)
    return norm


def _check_empty_optional_sanitizer() -> bool:
    from core.tool_emulation import sanitize_tool_calls_list

    schemas = {
        "read_file": {
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "optional": {"type": "string"},
                    "command": {"type": "string"},
                },
                "required": ["path"],
            }
        }
    }
    cleaned = sanitize_tool_calls_list(
        [{"name": "read_file", "arguments": {"path": "a", "optional": "", "command": ""}}],
        schemas,
    )
    return cleaned[0]["arguments"] == {"path": "a", "command": ""}


def _run_legacy_cases(chunk_chars: int) -> dict[str, bool]:
    from core.tool_emulation import StreamNormalizer, sanitize_tool_calls_list

    cases = [
        (_OPEN_TAG + '{"name":"read_file","arguments":{"path":"a"}}}}' + _CLOSE_TAG, 1),
        (_OPEN_TAG + '{"name":"read_file","arguments":""}' + _CLOSE_TAG, 0),
        ("Пример: `" + _OPEN_TAG + '{"name":"example"}' + _CLOSE_TAG + "` — это код.", 0),
        (
            "".join(
                _OPEN_TAG + '{"name":"read_file","arguments":{"path":"' + p + '"}}' + _CLOSE_TAG
                for p in ("a", "b", "c")
            ),
            3,
        ),
    ]
    checks: dict[str, bool] = {}
    for idx, (raw, count) in enumerate(cases):
        parser = StreamNormalizer(strict_live=False)
        _feed_chunked(parser, raw, chunk_chars)
        calls = sanitize_tool_calls_list([dict(call, index=99) for call in parser.tool_calls])
        checks[f"case_{idx}_count"] = len(calls) == count
        checks[f"case_{idx}_indices"] = [call["index"] for call in calls] == list(range(count))
        if idx == 0 and calls:
            checks["recovered_braces_arguments"] = calls[0]["arguments"] == {"path": "a"}
        if idx == 2:
            checks["inline_code_preserved"] = parser.content == raw
    checks["empty_optional_sanitized_payload_preserved"] = _check_empty_optional_sanitizer()
    return checks


def _check_incident_1(chunk_chars: int) -> dict[str, bool]:
    hybrid = (
        _OPEN_TAG + '{"name":"write","arguments":{"path":"p.py","content":"ok"}}' + _CLOSE_TAG
        + _OPEN_TAG
        + '{"name":"bash","arguments":{"description":"step73","command":"cat << \'PY\'\\n'
        + '{\n  "canary": "ok",\n  "nested": {"k": "v"}\n}\nPY"}}'
        + _CLOSE_TAG
    )
    odd_raw = (
        _OPEN_TAG
        + '{"name":"bash","arguments":{"description":"odd","command":"echo "hello\nPY"}}'
        + _CLOSE_TAG
    )
    lit_raw = (
        _OPEN_TAG
        + '{"name":"write","arguments":{"content":"s = \'{\\"a\\":1}' + _CLOSE_TAG + '\'"}}'
        + _CLOSE_TAG
    )
    norm = _parse_with_repair(hybrid, chunk_chars)
    odd_norm = _parse_with_repair(odd_raw, chunk_chars)
    lit_norm = _parse_with_repair(lit_raw, chunk_chars)
    return {
        "incident_1_hybrid_quote_drift": (
            len(norm.tool_calls) == 2
            and norm.tool_calls[1]["name"] == "bash"
            and '"canary": "ok"' in str(norm.tool_calls[1]["arguments"].get("command", ""))
        ),
        "incident_1_odd_quote": (
            len(odd_norm.tool_calls) == 1
            and odd_norm.tool_calls[0]["arguments"].get("command") == 'echo "hello\nPY'
        ),
        "incident_1_literal_close_preserved": (
            len(lit_norm.tool_calls) == 1
            and _CLOSE_TAG in str(lit_norm.tool_calls[0]["arguments"].get("content", ""))
        ),
    }


def _check_incident_2(chunk_chars: int) -> dict[str, bool]:
    from core.log_redaction import redact_log_text
    from core.tool_call_cap_policy import evaluate_call_cap
    from core.tool_emulation import StreamNormalizer
    from core.tool_turn_settle_policy import (
        ToolTurnSettleConfig,
        ToolTurnSettleState,
        decide_session_commit,
        evaluate_tool_turn_settle,
    )

    cap_dec = evaluate_call_cap(current_calls=64, incoming_calls=1, max_calls=64, cap_cutoff_enabled=True)
    settle = evaluate_tool_turn_settle(
        ToolTurnSettleState(
            now=10.0, has_error=False, has_open_tool_call=False, has_calls=True,
            last_open_chunk_ts=0.0, last_chunk_ts=10.0, calls_closed_ts=10.0, cap_cutoff=True,
        ),
        ToolTurnSettleConfig(),
    )
    commit_act = decide_session_commit(
        state="done", rc=0, tool_turn_stop=settle.tool_turn_stop, conversation_id="cid-1", cid_valid=True
    )
    accepted: list[dict[str, Any]] = []
    norm = StreamNormalizer(
        on_tool_call=lambda c: norm.suppress_tail() if len(accepted) >= 64 else accepted.append(c),
        strict_live=True,
    )
    stream = "".join(
        _OPEN_TAG + f'{{"name":"bash","arguments":{{"command":"echo {i}"}}}}' + _CLOSE_TAG
        for i in range(65)
    ) + "\n<tool_"
    _feed_chunked(norm, stream, chunk_chars)
    return {
        "incident_2_cap_cutoff_65_to_64": (
            cap_dec.action == "cap_cutoff" and len(accepted) == 64
            and redact_log_text(cap_dec.log_line) == cap_dec.log_line
        ),
        "incident_2_cid_invalidated": settle.tool_turn_stop is True and commit_act == "invalidate",
    }


def _check_incident_3(chunk_chars: int) -> dict[str, bool]:
    raw = (
        _OPEN_TAG + r'''{"name":"bash","arguments":{"command":"python3 -c 'print(\"\x27hi\x27\")'"}}''' + _CLOSE_TAG
        + _OPEN_TAG + r'{"name":"bash","arguments":{"command":"rg \"foo\s+bar\""}}' + _CLOSE_TAG
    )
    norm = _parse_with_repair(raw, chunk_chars)
    ok_x27 = len(norm.tool_calls) == 2 and r"\x27hi\x27" in str(norm.tool_calls[0]["arguments"].get("command", ""))
    ok_s = len(norm.tool_calls) == 2 and r"\s+" in str(norm.tool_calls[1]["arguments"].get("command", ""))
    return {"incident_3_invalid_escape_x27_and_s": ok_x27 and ok_s}


def run_wave_tools_incidents(bridge_fn: Callable[[], Any], chunk_chars: int) -> dict[str, bool]:
    """Полный набор проверок wave_4_tools (legacy + инциденты #1/#2/#3)."""
    _ = bridge_fn()
    checks = _run_legacy_cases(chunk_chars)
    checks.update(_check_incident_1(chunk_chars))
    checks.update(_check_incident_2(chunk_chars))
    checks.update(_check_incident_3(chunk_chars))
    return checks

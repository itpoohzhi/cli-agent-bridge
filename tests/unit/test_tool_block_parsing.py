"""L1: разбор `<tool_call>`, курсор `</tool_call>`, O(1)-редактура, `read_number` и settle."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import types
from dataclasses import replace
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import recovery_flags as rf  # noqa: E402
from core import tool_emulation as te  # noqa: E402
from core.log_redaction import redact_log_text  # noqa: E402
from core.tool_block_parsing import (  # noqa: E402
    ToolCloseCursor,
    advance_tool_close_scan,
    find_tool_close_outside_string,
    format_malformed_tool_block_log,
    loads_tolerant_json,
    recover_trailing_braces,
    repair_invalid_single_quote_escape,
)
from core.tool_turn_settle_policy import (  # noqa: E402
    ToolTurnSettleConfig,
    ToolTurnSettleState,
    evaluate_tool_turn_settle,
)


def _load_muse_tool_parser() -> types.ModuleType:
    path = _ROOT / "bridges" / "muse-bridge" / "muse_runtime" / "tool_parser.py"
    spec = importlib.util.spec_from_file_location("muse_runtime_tool_parser_l1", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["muse_runtime_tool_parser_l1"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_agy_server() -> types.ModuleType:
    name = "agy_bridge_server_l1"
    if name in sys.modules:
        return sys.modules[name]
    path = _ROOT / "bridges" / "agy-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_repair_invalid_single_quote_escape_handles_slashes_and_outside_strings() -> None:
    raw = r"""{"a":"it\'s \"ok\"","b":"keep \\'here\\'","c":"odd \\\'fix\\\'"}"""
    repaired = repair_invalid_single_quote_escape(raw)
    assert repaired == r"""{"a":"it's \"ok\"","b":"keep \\'here\\'","c":"odd \\'fix\\'"}"""
    assert json.loads(repaired) == {"a": 'it\'s "ok"', "b": r"keep \'here\'", "c": r"odd \'fix\'"}
    outside = r"""prefix \'outside\' {"k":"in\'"}"""
    assert repair_invalid_single_quote_escape(outside) == r"""prefix \'outside\' {"k":"in'"}"""
    raw_eof = r'{"a":"x\'","b":"' + "\\"
    assert repair_invalid_single_quote_escape(raw_eof) == '{"a":"x\'","b":"' + "\\"


def test_trailing_comma_removal_is_string_aware() -> None:
    payload = r'{"cmd": "echo \"[1,]\" {a,}", "arr": [1, 2, ], "nested": {"x": 1, }, }'
    parsed = loads_tolerant_json(payload)
    assert isinstance(parsed, dict)
    assert parsed["cmd"] == 'echo "[1,]" {a,}'
    assert parsed == {
        "cmd": 'echo "[1,]" {a,}',
        "arr": [1, 2],
        "nested": {"x": 1},
    }


def test_recover_trailing_braces_boundaries() -> None:
    assert recover_trailing_braces('  {"name": "bash"} }} \n') == {"name": "bash"}
    assert recover_trailing_braces('{"name": "bash"}') is None
    assert recover_trailing_braces('{"a": 1}}}}', max_extra_braces=2) is None
    assert recover_trailing_braces("[1, 2]}}") is None
    assert recover_trailing_braces('{"a": 1}} trailing') is None


def test_loads_tolerant_json_order_and_errors() -> None:
    strict_src = '{"literal": "a,}"}'
    assert loads_tolerant_json(strict_src) == {"literal": "a,}"}

    repaired_only = r'''{"cmd":"echo \'ok\'"}'''
    assert loads_tolerant_json(repaired_only) == {"cmd": "echo 'ok'"}

    combined = r'''{"name":"bash","args":{"cmd":"echo \'hi\'",},}}}'''
    assert loads_tolerant_json(combined) == {"name": "bash", "args": {"cmd": "echo 'hi'"}}

    with pytest.raises(ValueError):
        _ = loads_tolerant_json('{"broken":')

    with pytest.raises(ValueError):
        _ = loads_tolerant_json('{"a": 1}}}}}}}}}}}}}}}}}}')

    with pytest.raises(ValueError, match="nested too deeply"):
        _ = loads_tolerant_json("[" * 60000 + "]" * 60000)


def test_tool_close_cursor_chunk_invariance_reset_and_linear_time() -> None:
    payload = '{"q":"a \\"x\\" </tool_call> \\\\\\" </tool_call> ok"}</tool_call>rest'
    expected = find_tool_close_outside_string(payload)
    assert expected == payload.rindex("</tool_call>")
    assert find_tool_close_outside_string('{"q":"\\\\"}</tool_call>') == 10

    for step in (1, 3, 7):
        cur = ToolCloseCursor()
        buf = ""
        found = -1
        for i in range(0, len(payload), step):
            buf += payload[i : i + step]
            found = cur.find_close(buf, start=0)
            if found != -1:
                break
        assert found == expected

    cur = ToolCloseCursor(close_tag="</custom>")
    assert advance_tool_close_scan(cur, '{"x":"</custom>"}</cust', start=0) == -1
    assert advance_tool_close_scan(cur, '{"x":"</custom>"}</custom>', start=0) == 17
    assert advance_tool_close_scan(cur, "ok</custom>", start=0) == 2  # shrink resets cursor

    big = '{"cmd":"' + ("a" * (2 * 1024 * 1024)) + '"}</tool_call>'
    big_cur = ToolCloseCursor()
    t0 = time.perf_counter()
    hit = -1
    for end in range(4096, len(big) + 4096, 4096):
        hit = big_cur.find_close(big[:end], start=0)
        if hit != -1:
            break
    assert hit == len(big) - len("</tool_call>")
    assert time.perf_counter() - t0 < 2.0


def test_format_malformed_tool_block_log_10mib_and_edge_straddle_redaction() -> None:
    pad = "x" * (5 * 1024 * 1024)
    straddle_tok = "tok_edge_secret_998877"
    secret_mid = "sk-proj-edge_secret_alpha_123456"
    raw = (
        f'{pad}{{"api_key":"{secret_mid}","hdr":"Authorization: Bearer {straddle_tok}",'
        + '"x":"1234567890","bad":\'oops}'
        + pad
    )
    err_pos = raw.index(":'oops")
    seen: list[str] = []

    def spy_redact(chunk: str) -> str:
        seen.append(chunk)
        return redact_log_text(chunk)

    t0 = time.perf_counter()
    out = format_malformed_tool_block_log(
        raw, err_pos=err_pos, window_chars=40, redact_margin_chars=256, redact_fn=spy_redact
    )
    assert time.perf_counter() - t0 < 0.5
    assert out.startswith("malformed tool_call block raw=")
    assert ":'oops" in out
    assert straddle_tok not in out
    assert secret_mid not in out
    assert seen and all(chunk in raw and len(chunk) <= 2 * (40 + 256) for chunk in seen)


def test_format_malformed_tool_block_log_err_pos_inside_jwt_zero_leakage() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6y"
    raw = f'{{"auth":"Bearer {jwt}","k":"sk-proj-inside_token_999999"}}'
    err_pos = raw.index("eyJzdWI")
    out = format_malformed_tool_block_log(
        raw, err_pos=err_pos, window_chars=32, redact_margin_chars=256, redact_fn=redact_log_text
    )
    assert out.startswith("malformed tool_call block raw=")
    assert "***" in out
    assert "eyJ" not in out
    assert "SflKxw" not in out
    assert "sk-proj" not in out


def test_diagnostic_window_config_and_read_number_bool_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    monkeypatch.setenv(rf.CONFIG_PATH_ENV, str(cfg))
    monkeypatch.delenv(rf.DIAGNOSTIC_WINDOW_ENV, raising=False)
    monkeypatch.delenv(rf.DIAGNOSTIC_MARGIN_ENV, raising=False)

    assert rf.read_diagnostic_window_chars() == 120
    assert rf.read_diagnostic_redact_margin_chars() == 2048

    _ = cfg.write_text(json.dumps({"N": True, rf.DIAGNOSTIC_WINDOW_ENV: 64}), encoding="utf-8")
    assert rf.read_number("N", 7.0, (0.0, 10.0), {}, {"N": True}) == 7.0
    assert rf.read_number("N", 7.0, (0.0, 10.0), {}, {"N": False}) == 7.0
    assert rf.read_number("N", 7.0, (0.0, 10.0), {}, {"N": None}) == 7.0
    assert rf.read_number("N", 7.0, (0.0, 10.0), {}, {"N": "4.5"}) == 4.5
    assert rf.read_diagnostic_window_chars() == 64

    monkeypatch.setenv(rf.DIAGNOSTIC_WINDOW_ENV, "256")
    monkeypatch.setenv(rf.DIAGNOSTIC_MARGIN_ENV, "512")
    assert rf.read_diagnostic_window_chars() == 256
    assert rf.read_diagnostic_redact_margin_chars() == 512

    monkeypatch.setenv(rf.DIAGNOSTIC_WINDOW_ENV, "16")
    assert rf.read_diagnostic_window_chars() == 64


def test_muse_bridge_reexports_match_core_domain() -> None:
    muse_tp = _load_muse_tool_parser()
    assert te.__dict__["_loads_tolerant"] is loads_tolerant_json
    assert te.__dict__["_recover_trailing_braces"] is recover_trailing_braces
    assert te.__dict__["_find_tool_close_outside_string"] is find_tool_close_outside_string
    assert muse_tp.__dict__["_loads_tolerant"] is loads_tolerant_json
    assert muse_tp.__dict__["_recover_trailing_braces"] is recover_trailing_braces


def test_tool_turn_settle_post_call_suppressed_clean_complete() -> None:
    cfg = ToolTurnSettleConfig(settle_timeout_s=5.0, stall_timeout_s=30.0, eof_grace_s=1.5)
    base = ToolTurnSettleState(
        now=107.0,
        has_error=False,
        has_open_tool_call=False,
        has_calls=True,
        last_open_chunk_ts=100.0,
        last_chunk_ts=100.0,
        calls_closed_ts=100.0,
        proc_exited=False,
        result_received=False,
        post_call_suppressed=True,
    )
    clean = evaluate_tool_turn_settle(base, cfg)
    assert clean.action == "clean_complete"
    assert clean.should_stop is True
    assert clean.tool_turn_stop is False
    assert clean.tool_turn_clean_eof is True

    forced = evaluate_tool_turn_settle(replace(base, post_call_suppressed=False), cfg)
    assert forced.action == "forced_stop"
    assert forced.should_stop is True
    assert forced.tool_turn_stop is True
    assert forced.tool_turn_clean_eof is False


def test_agy_tool_turn_cutoff_and_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    srv = _load_agy_server()
    monkeypatch.setenv(rf.CONFIG_PATH_ENV, str(_ROOT / ".nonexistent-l1-cfg.json"))
    monkeypatch.setenv(rf.POST_CALL_CUTOFF_FLAG_ENV, "1")
    monkeypatch.setattr(srv, "_log", lambda *_a, **_kw: None)
    tools = [{"type": "function", "function": {"name": "bash", "parameters": {"type": "object"}}}]
    seen_calls: list[dict[str, object]] = []
    turn = srv._ToolTurn(tools, lambda _s: True, lambda _s: True, lambda cs: seen_calls.extend(cs) is None)
    assert turn.feed('<tool_call>{"name":"bash","arguments":{"cmd":"ok"}}</tool_call></tool_call>') is True
    assert turn.ok is True and turn.error == "" and len(seen_calls) == 1
    assert turn._normalizer.post_call_suppressed is True
    assert turn.feed("x" * (turn._max_bytes + 16)) is True
    assert turn.error == ""
    stale_ts = time.monotonic() - (turn._settle_cfg.settle_timeout_s + turn._settle_cfg.eof_grace_s + 2.0)
    turn._calls_closed_ts = turn._last_chunk_ts = stale_ts
    dec = turn.settle_decision()
    assert dec.action == "clean_complete" and dec.tool_turn_clean_eof is True

    turn2 = srv._ToolTurn(tools, lambda _s: True, lambda _s: True, lambda _cs: True)

    def _boom() -> None:
        raise te.LiveParserError("")

    turn2._run_normalizer(_boom, "feed")
    assert turn2.error == "LiveParserError"
    assert turn2.feed("x" * (turn2._max_bytes + 16)) is True
    assert turn2.error == "LiveParserError"

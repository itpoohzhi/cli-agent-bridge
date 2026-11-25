"""L1: ремонт невалидных JSON-escape (REQ-006) и неэкранированных `"` (REQ-001)."""

from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.tool_block_parsing import loads_tolerant_json  # noqa: E402
from core.tool_json_repair import (  # noqa: E402
    DEFAULT_MAX_QUOTE_CANDIDATES,
    repair_invalid_json_escapes,
    repair_unescaped_json_quotes,
)


def test_repair_invalid_escapes_x27_preserves_bash_and_python_ast() -> None:
    raw = r'''{"name":"bash","arguments":{"command":"python3 -c 'run_js(\"\x27hi\x27\")'"}}'''
    with pytest.raises(ValueError):
        _ = loads_tolerant_json(raw, json_repair_enabled=False)
    parsed = loads_tolerant_json(raw, json_repair_enabled=True)
    assert isinstance(parsed, dict)
    cmd = str(parsed["arguments"]["command"])
    assert cmd == r"""python3 -c 'run_js("\x27hi\x27")'"""
    assert cmd.count("'") == 2
    py_src = cmd.split("'", 2)[1]
    tree = ast.parse(py_src)
    assert isinstance(tree, ast.Module) and len(tree.body) == 1


def test_repair_invalid_escapes_regex_paths_and_incomplete_unicode() -> None:
    raw = r'{"a":"\s\d\w\.\1\0\$","b":"C:\users\work\u12\uZZZZ","c":"\u041f\u0027"}'
    repaired = repair_invalid_json_escapes(raw)
    parsed = json.loads(repaired)
    assert parsed == {
        "a": r"\s\d\w\.\1\0\$",
        "b": r"C:\users\work\u12\uZZZZ",
        "c": "П'",
    }


def test_repair_invalid_escapes_single_quote_idempotency_and_valid_json() -> None:
    single = r'''{"a":"it\'s","b":"keep \\'here\\'","c":"\\x27"}'''
    once = repair_invalid_json_escapes(single)
    assert once == repair_invalid_json_escapes(once)
    assert json.loads(once) == {"a": "it's", "b": r"keep \'here\'", "c": r"\x27"}

    valid = r'{"cmd":"echo \"ok\"\n\t\\path\\x27","u":"\u0041"}'
    assert repair_invalid_json_escapes(valid) == valid
    assert loads_tolerant_json(valid, json_repair_enabled=True) == json.loads(valid)
    assert repair_invalid_json_escapes(r'outside \x27 {"k":"in\s"}') == r'outside \x27 {"k":"in\\s"}'


def _build_step73_hybrid_payload() -> str:
    prefix = r'''python3 - << 'PY'\nimport json\nprint(\"header\")\n'''
    nested_rows = ",\n".join(f'  "probe_{i}": {{"canary": "ok", "eval_key": "k{i}"}}' for i in range(10))
    body = prefix + "doc = {\n" + nested_rows + '\n}\ntriple = """\n' + ("\n" * 52) + '"""\nPY'
    return '{"name":"bash","arguments":{"description":"step73","command":"' + body + '"}}'


def test_repair_unescaped_quotes_step73_hybrid_drift() -> None:
    raw = _build_step73_hybrid_payload()
    assert raw.count("\n") >= 60
    assert raw.count('"') >= 62
    with pytest.raises(ValueError):
        _ = loads_tolerant_json(raw, json_repair_enabled=False)
    parsed = loads_tolerant_json(raw, json_repair_enabled=True)
    assert isinstance(parsed, dict)
    assert parsed["name"] == "bash"
    args = parsed["arguments"]
    assert args["description"] == "step73"
    assert '"canary": "ok"' in args["command"]
    assert args["command"].endswith("PY")


def test_repair_unescaped_quotes_schema_disambiguation_command_before_description() -> None:
    raw = '{"name":"bash","arguments":{"command":"echo "hello", "k": "v"","description":"Run echo"}}'
    # Без схемы неоднозначно -> fail-closed
    assert repair_unescaped_json_quotes(raw) is None
    allowed = frozenset({"command", "description"})
    required = frozenset({"command", "description"})
    repaired_req = repair_unescaped_json_quotes(raw, allowed_arg_keys=allowed, required_arg_keys=required)
    assert repaired_req is not None
    parsed = json.loads(repaired_req)
    assert parsed["arguments"] == {"command": 'echo "hello", "k": "v"', "description": "Run echo"}

    # Работает и когда description опционально (required только command)
    repaired_opt = repair_unescaped_json_quotes(
        raw, allowed_arg_keys=allowed, required_arg_keys=frozenset({"command"})
    )
    assert repaired_opt == repaired_req


def test_repair_unescaped_quotes_fail_closed_ambiguous_duplicate_and_truncated() -> None:
    ambiguous = '{"command": "echo "a", "foo": "b"}'
    assert repair_unescaped_json_quotes(ambiguous) is None
    with pytest.raises(ValueError):
        _ = loads_tolerant_json(ambiguous, json_repair_enabled=True)

    dup = '{"name":"bash","arguments":{"command": "echo "x", "command": "rm -rf /"}}'
    assert repair_unescaped_json_quotes(dup) is None
    assert repair_unescaped_json_quotes(
        dup, allowed_arg_keys=frozenset({"command"}), required_arg_keys=frozenset({"command"})
    ) is None

    truncated = '{"name": "bash", "arguments": {"command": "abc'
    assert repair_unescaped_json_quotes(truncated) is None
    assert repair_unescaped_json_quotes('{"broken_key: "v"}') is None


def test_repair_unescaped_quotes_dos_budget_is_linear_and_fast() -> None:
    chunk = '", "k": "v'
    many = '{"command":"echo "x' + (chunk * (DEFAULT_MAX_QUOTE_CANDIDATES + 40)) + '"}'
    t0 = time.perf_counter()
    assert repair_unescaped_json_quotes(many) is None
    assert time.perf_counter() - t0 < 0.5

    big = '{"command":"echo "x' + ("a" * (1024 * 1024)) + '"}'
    t1 = time.perf_counter()
    repaired = repair_unescaped_json_quotes(big)
    elapsed = time.perf_counter() - t1
    assert repaired is not None
    assert elapsed < 0.5
    assert json.loads(repaired)["command"].startswith('echo "xaaa')


def test_combined_odd_quote_and_invalid_escape_stage_2b() -> None:
    raw = r'{"name":"bash","arguments":{"command":"echo "odd \x27hi\x27 \s+ end"}}'
    with pytest.raises(ValueError):
        _ = loads_tolerant_json(raw, json_repair_enabled=False)
    parsed = loads_tolerant_json(raw, json_repair_enabled=True)
    assert isinstance(parsed, dict)
    assert parsed["arguments"]["command"] == r'echo "odd \x27hi\x27 \s+ end'


def test_tolerant_json_strips_single_trailing_semicolon_only_when_repair_enabled() -> None:
    raw = '{"name":"read","arguments":{"limit":200,"offset":1}};'
    parsed = loads_tolerant_json(raw, json_repair_enabled=True)
    assert isinstance(parsed, dict)
    assert parsed["name"] == "read"
    assert parsed["arguments"] == {"limit": 200, "offset": 1}

    with pytest.raises(ValueError):
        _ = loads_tolerant_json(raw, json_repair_enabled=False)


@pytest.mark.parametrize(
    "raw",
    [
        ";;",
        "{<json>}",
        '{"a":1}";',
        '{"a":1};"',
        '{"a":"\\q"};',
        '{"a":1,};',
        '{"a":1}}};',
        '{"a":1,"a":2};',
        '{"a":NaN};',
        "[1,2];",
        '{"a":"raw\nnewline"};',
    ],
)
def test_tolerant_json_combined_suffix_negatives_fail_closed(raw: str) -> None:
    with pytest.raises(ValueError):
        _ = loads_tolerant_json(raw, json_repair_enabled=True)

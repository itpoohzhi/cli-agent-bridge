"""L1 contract tests for pure core/zc_admission: purity, ingress, sabotage matrix, wire parity."""

from __future__ import annotations

import ast
import json
from typing import Any

import pytest

from core.stdio_resident.codex_driver import _build_thread_params, _build_turn_params
from core.zc_admission import (
    TurnProofRecorder,
    ZeroCanonAdmissionError,
    build_thread_params,
    build_turn_params,
    decide_ingress,
    error_body,
    evaluate_admission,
    is_valid_server_thread_id,
    sanitize_model_id,
)
from scripts._codex_mmod_check import ROOT, _fn_metrics, _functions, check_pure_zero_io

MODULE_REL = "core/zc_admission.py"
MODULE_SRC = (ROOT / MODULE_REL).read_text(encoding="utf-8")
MATRIX = {"gpt-6.1-sol": ("low", "medium", "high", "xhigh", "max"), "gpt-6.1-terra": ("low", "medium", "high")}
DEFAULTS = {"gpt-6.1-sol": "high", "gpt-6.1-terra": "high"}
ALLOWED_IMPORT_ROOTS = {"__future__", "json", "re", "collections", "dataclasses", "typing"}


def test_l1_pure_zero_io_and_leaf_module() -> None:
    tree = ast.parse(MODULE_SRC)
    assert check_pure_zero_io(MODULE_REL, tree) == []
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    assert "core" not in roots and "scripts" not in roots
    assert roots <= ALLOWED_IMPORT_ROOTS


def test_l1_loc_and_function_budgets() -> None:
    for rel, cap in ((MODULE_REL, 240), ("tests/test_zc_admission_contract.py", 260)):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from __future__ import annotations" in src
        assert src.count("\n") + int(not src.endswith("\n")) <= cap
        for name, node in _functions(ast.parse(src)).items():
            floc, params, cc = _fn_metrics(node)
            assert floc <= 50 and params <= 5 and cc <= 10, f"{rel}:{name} loc={floc} params={params} cc={cc}"


def test_decide_ingress_explicit_and_default_effort() -> None:
    assert decide_ingress(" GPT-6.1-Sol ", " XHIGH ", MATRIX, DEFAULTS) == ("gpt-6.1-sol", "xhigh")
    assert decide_ingress("gpt-6.1-terra", None, MATRIX, DEFAULTS) == ("gpt-6.1-terra", "high")
    assert decide_ingress("gpt-6.1-sol", "   ", MATRIX, DEFAULTS) == ("gpt-6.1-sol", "high")
    assert decide_ingress("gpt-6.1-sol", "low", MATRIX, DEFAULTS) == ("gpt-6.1-sol", "low")


@pytest.mark.parametrize(
    ("model", "effort", "code"),
    [
        (None, None, "unsupported_model"),
        ("", "high", "unsupported_model"),
        ("   ", None, "unsupported_model"),
        ("gpt-9-ultra", "high", "unsupported_model"),
        ("gpt-6.1-terra", "xhigh", "unsupported_model_effort"),
        ("gpt-6.1-terra", "max", "unsupported_model_effort"),
        ("gpt-6.1-sol", "ultra", "unsupported_model_effort"),
    ],
)
def test_decide_ingress_fail_closed_no_silent_clamp(model: str | None, effort: str | None, code: str) -> None:
    with pytest.raises(ZeroCanonAdmissionError) as exc:
        decide_ingress(model, effort, MATRIX, DEFAULTS)
    assert exc.value.code == code and exc.value.http_status == 400


def test_decide_ingress_sanitizes_model_id_in_message() -> None:
    with pytest.raises(ZeroCanonAdmissionError) as exc:
        decide_ingress("bad\r\n\x00model\x1f", None, MATRIX, DEFAULTS)
    assert "badmodel" in exc.value.message and "\r" not in exc.value.message and "\x00" not in exc.value.message
    long_model = "x" * 300
    with pytest.raises(ZeroCanonAdmissionError) as exc:
        decide_ingress(long_model, None, MATRIX, DEFAULTS)
    assert "x" * 128 in exc.value.message and "x" * 129 not in exc.value.message


def test_sanitize_model_id() -> None:
    assert sanitize_model_id(" a\r\nb\x00c\x1fd\x7f ") == "abcd"
    assert sanitize_model_id("m" * 200) == "m" * 128
    assert sanitize_model_id("m" * 200, 10) == "m" * 10
    assert sanitize_model_id(None) == ""


@pytest.mark.parametrize("bad", ["", "   ", None, "th-1", "TH-99", "probe", "PROBE", "thr\n1", "a b", "x\x7fy", 7])
def test_thread_id_rejects_invalid(bad: Any) -> None:
    assert is_valid_server_thread_id(bad) is False


def test_thread_id_accepts_server_issued() -> None:
    assert is_valid_server_thread_id("thr-srv-abc123") is True


def _good_recorder() -> TurnProofRecorder:
    rec = TurnProofRecorder()
    rec.record_handshake(True)
    rec.record_clean_home(True)
    rec.record_thread("thr-srv-abc123", 1)
    rec.record_turn("turn-abc", 1)
    return rec


SABOTAGE: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    ("no_recorder", {"recorder": None}, {}),
    ("handshake_false", {"handshake_acked": False}, {}),
    ("clean_home_false", {"clean_home_verified": False}, {}),
    ("inherited_state", {"inherited_state": True}, {}),
    ("tool_event", {"tool_events_seen": 1}, {}),
    ("empty_thread", {"issued_thread_id": ""}, {"thread_id": ""}),
    ("client_thread_th", {}, {"thread_id": "th-1"}),
    ("probe_thread", {}, {"thread_id": "probe"}),
    ("thread_mismatch", {}, {"thread_id": "thr-srv-other"}),
    ("empty_turn_tautology", {"issued_turn_id": ""}, {"turn_id": ""}),
    ("turn_mismatch", {}, {"turn_id": "turn-other"}),
    ("zero_epoch_tautology", {"turn_epoch": 0}, {"epoch": 0}),
    ("bool_epoch_trap", {}, {"epoch": True}),
    ("epoch_mismatch", {}, {"epoch": 2}),
]


@pytest.mark.parametrize(("case", "rec_over", "call_over"), SABOTAGE, ids=[c[0] for c in SABOTAGE])
def test_evaluate_admission_sabotage_fails_closed(case: str, rec_over: dict[str, Any], call_over: dict[str, Any]) -> None:
    rec = None if rec_over.get("recorder", "keep") is None else _good_recorder()
    if rec is not None:
        for key, val in rec_over.items():
            setattr(rec, key, val)
    args: dict[str, Any] = {"thread_id": "thr-srv-abc123", "turn_id": "turn-abc", "epoch": 1, **call_over}
    with pytest.raises(ZeroCanonAdmissionError) as exc:
        evaluate_admission(rec, args["thread_id"], args["turn_id"], args["epoch"])
    assert exc.value.code == "zero_canon_attestation_failed" and exc.value.http_status == 502, case


def test_evaluate_admission_happy_path_and_tool_relaxation() -> None:
    assert evaluate_admission(_good_recorder(), "thr-srv-abc123", "turn-abc", 1) is None
    rec = _good_recorder()
    rec.record_tool_event()
    assert evaluate_admission(rec, "thr-srv-abc123", "turn-abc", 1, require_zero_tools=False) is None


def test_recorder_methods_and_snapshot_isolation() -> None:
    rec = TurnProofRecorder()
    rec.record_handshake(True)
    rec.record_clean_home(True)
    rec.record_thread(" thr-srv-abc123 ", 2)
    rec.record_turn(" turn-abc ", 3)
    rec.record_tool_event()
    snap = rec.snapshot()
    assert snap == rec and snap is not rec
    rec.record_tool_event()
    assert (snap.tool_events_seen, rec.tool_events_seen) == (1, 2)
    assert (snap.issued_thread_id, snap.issued_turn_id, snap.turn_epoch) == ("thr-srv-abc123", "turn-abc", 3)
    assert snap.handshake_acked and snap.clean_home_verified and not snap.inherited_state


def test_error_body_deterministic_utf8_bytes() -> None:
    body = error_body("boom", "Ошибка апстрима")
    assert body == error_body("boom", "Ошибка апстрима")
    expected = '{"error":{"message":"Ошибка апстрима","type":"upstream_error","code":"boom"}}'
    assert body == expected.encode("utf-8") and len(body) == len(expected.encode("utf-8"))
    assert json.loads(body.decode("utf-8"))["error"]["message"] == "Ошибка апстрима"
    assert "Ошибка".encode("utf-8") in body  # ensure_ascii=False: raw Cyrillic bytes, no \\u escapes


def test_error_body_sanitizes_model_id_and_custom_type() -> None:
    body = error_body("bad", "fail", err_type="invalid_request_error", model_id="m\r\n\x00" + "z" * 200)
    payload = json.loads(body.decode("utf-8"))["error"]
    assert payload["type"] == "invalid_request_error" and payload["code"] == "bad"
    assert "m" + "z" * 127 in payload["message"] and "z" * 128 not in payload["message"]
    assert "\r" not in payload["message"] and "\x00" not in payload["message"]


CTX_CASES: list[dict[str, Any]] = [
    {},
    {"model": "default", "cwd": ""},
    {"model": "gpt-6.1-sol", "cwd": "/w", "effort": "high", "input": [{"type": "text", "text": "hi"}]},
    {"model": "", "effort": "default", "input": "not-a-list", "cwd": 5},
    {"model": 42, "effort": None},
]


@pytest.mark.parametrize("ctx", CTX_CASES)
@pytest.mark.parametrize("zc", [True, False])
def test_wire_param_builders_parity_with_driver(ctx: dict[str, Any], zc: bool) -> None:
    assert build_thread_params(ctx, zc) == _build_thread_params(ctx, zc)
    assert build_turn_params("p", ctx, zc) == _build_turn_params("p", ctx, zc)


def test_wire_param_builders_exact_shape() -> None:
    ctx = {"model": "gpt-6.1-sol", "cwd": "/w", "effort": "high", "input": [{"type": "text"}]}
    assert build_thread_params(ctx, True) == {"ephemeral": True, "zero_canon": True, "model": "gpt-6.1-sol", "cwd": "/w"}
    assert build_turn_params("p", ctx, False) == {
        "prompt": "p", "zero_canon": False, "input": [{"type": "text"}], "model": "gpt-6.1-sol", "effort": "high",
    }

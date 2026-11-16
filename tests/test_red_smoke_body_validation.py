"""C2-6: позитивное тело, gated H-2/H-2b и безопасные receipt, без сети/процессов."""
from __future__ import annotations

import argparse
import builtins
import copy
import importlib
import io
import json
import os
import socket
import subprocess
import sys
import time
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
SSE, JSON = "text/event-stream", "application/json"
DONE = b"data: [DONE]\n\n"
BOUNDS = [
    ("BRIDGE_HALF_OPEN_LEASE_TTL_S", 60, 5, 600),
    ("BRIDGE_CATALOG_TTL_S", 60, 5, 600),
    ("MODEL_NOTES_REFRESH_INTERVAL_S", 30, 5, 300),
    ("MODEL_NOTES_READ_TIMEOUT_S", 2, 0.01, 10),
    ("MODEL_NOTES_STALE_GRACE_S", 60, 0, 60),
    ("CLOCK_SKEW_TOLERANCE_S", 5, 0, 60),
]
def _forbidden(*args: Any, **kwargs: Any) -> Any:
    pytest.fail("L1 запрещает сеть, запуск процессов и sleep")
@pytest.fixture()
def smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("HOME", str(tmp_path))
    module = importlib.import_module("scripts.smoke_models")
    monkeypatch.setattr(module, "_resolve_api_key", lambda _: "synthetic-l1")
    monkeypatch.setattr(module, "build_bridge_payload", lambda *a, **k: {"stream": k.get("stream", True)})
    for owner, name in ((socket, "socket"), (socket, "create_connection"),
                        (subprocess, "Popen"), (os, "system"), (time, "sleep"),
                        (module.urllib.request, "urlopen")):
        monkeypatch.setattr(owner, name, _forbidden)
    return module
def _body(value: Any, content_type: str = SSE) -> bytes:
    encoded = json.dumps(value, ensure_ascii=False).encode()
    return b"data: " + encoded + b"\n\n" if content_type == SSE else encoded
def _answer(text: str, field: str = "delta") -> dict[str, Any]:
    return {"choices": [{field: {"content": text}, "finish_reason": "stop"}]}
class Response(io.BytesIO):
    def __init__(self, body: bytes, content_type: str) -> None:
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.status = 200

    def getcode(self) -> int:
        return self.status
def _smoke(smoke: Any, monkeypatch: pytest.MonkeyPatch, case: tuple[str, bytes]) -> bool:
    content_type, body = case
    monkeypatch.setattr(smoke.urllib.request, "urlopen", lambda *a, **k: Response(body, content_type))
    ok, _, _ = smoke.smoke_test_model("http://l1.invalid/v1", "l1-model", 20.0, None, "", "", False, True, False)
    return ok
@pytest.mark.parametrize("case", [
    (SSE, b""), (SSE, DONE), (SSE, _body(_answer("")) + DONE),
    (SSE, _body(_answer(" \n\t")) + DONE),
    (SSE, _body({"choices": [{"delta": {"reasoning_content": "thinking"}}]}) + DONE),
    (SSE, _body(_answer("partial"))), (SSE, _body(_answer("quota exceeded")) + DONE),
    (SSE, _body(_answer("ok")) + _body({"error": {"message": "failed"}}) + DONE),
    (SSE, _body(_answer("ok")) + DONE + _body(_answer("late"))),
    (SSE, b"data: {broken}\n\n" + DONE),
    (JSON, b""), (JSON, b"{}"), (JSON, b'{"choices":'),
    (JSON, _body({"error": {"message": "failed"}}, JSON)),
    (JSON, _body(_answer("", "message"), JSON)),
    (JSON, _body(_answer("quota exceeded", "message"), JSON)),
])
def test_http_200_without_useful_terminal_body_never_passes(
    smoke: Any, monkeypatch: pytest.MonkeyPatch, case: tuple[str, bytes],
) -> None:
    assert _smoke(smoke, monkeypatch, case) is False

@pytest.mark.parametrize("case", [
    (SSE, _body(_answer("PONG")) + DONE),
    (JSON, _body(_answer("PONG", "message"), JSON)),
    (SSE, _body({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "call-l1", "type": "function",
         "function": {"name": "read", "arguments": "{}"}},
    ]}, "finish_reason": "tool_calls"}]}) + DONE),
])
def test_useful_content_or_tool_call_is_positive_control(
    smoke: Any, monkeypatch: pytest.MonkeyPatch, case: tuple[str, bytes],
) -> None:
    assert _smoke(smoke, monkeypatch, case) is True

def test_smoke_uses_core_outcome(smoke: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = importlib.import_module("core.stream_outcome")
    instance = Mock(wraps=outcome.StreamOutcomeClassifier(status=200, content_type=SSE))
    factory = Mock(return_value=instance)
    monkeypatch.setattr(outcome, "StreamOutcomeClassifier", factory)
    monkeypatch.setattr(smoke, "StreamOutcomeClassifier", factory, raising=False)
    body = _body(_answer("PONG")) + DONE
    assert _smoke(smoke, monkeypatch, (SSE, body)) is True
    factory.assert_called_once()
    assert b"".join(call.args[0] for call in instance.feed.call_args_list) == body
    instance.finish.assert_called_once()
    monkeypatch.setattr(smoke.urllib.request, "urlopen", Mock(side_effect=RuntimeError("synthetic-l1")))
    assert "synthetic-l1" not in smoke.smoke_test_model("http://l1.invalid/v1", "l1-model")[1]
def test_stage4_flags_are_parsed_without_launching(smoke: Any, tmp_path: Path) -> None:
    receipt, launch = tmp_path / "receipt.json", tmp_path / "argv.json"
    argv = ["--live", "--run-id", "l1-run", "--v2safe-live-receipt", str(receipt),
            "--launch-argv-json", str(launch)]
    args = smoke.build_parser().parse_args(argv)
    assert args.live and args.run_id == "l1-run"
    assert Path(args.v2safe_live_receipt) == receipt and Path(args.launch_argv_json) == launch
    assert smoke.main(argv + ["--dry-run", "--probe-model", "l1-model"]) == 0
    assert not receipt.exists()
@pytest.mark.parametrize("launch", [False, True])
def test_main_blocks_missing_launch_before_live_work(
    smoke: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str], launch: bool,
) -> None:
    argv = ["--live", "--v2safe-live-receipt", str(tmp_path / "receipt.json")]
    if launch:
        argv += ["--launch-argv-json", str(tmp_path / "missing.json")]
    with pytest.raises(SystemExit) as error:
        smoke.main(argv)
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "launch-argv-json" in stderr and "unrecognized arguments" not in stderr

def _launch_parser(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument("--round-dir", required=True)
    parser.add_argument("--slot", required=True, choices=["l1-slot"])
    parser.add_argument("--transport", required=True, choices=["l1-transport"])
    return parser.parse_args(argv[2:])

def _launch_argv() -> list[str]:
    return [sys.executable, "/canonical/launch_seat.py", "--round-dir", "/l1/round",
            "--slot", "l1-slot", "--transport", "l1-transport"]

@pytest.mark.parametrize("value", [
    None, True, {}, [], [1], [""], ["python", "x\u0000y"], "{broken",
    "python launch_seat.py; touch /l1/never", ["/bin/sh", "-c", "touch /l1/never"],
    ["/bin/sh", "/canonical/launch_seat.py", "--round-dir", "/l1/round", "--slot", "l1-slot", "--transport", "l1-transport"], [sys.executable, "-c", "exec('payload')"],
])
def test_launch_rejects_shell_and_invalid_argv(smoke: Any, tmp_path: Path, value: Any) -> None:
    path = tmp_path / "argv.json"
    path.write_text(value if value == "{broken" else json.dumps(value))
    with pytest.raises((ValueError, argparse.ArgumentError, SystemExit)):
        smoke.load_launch_argv(path, Mock(side_effect=_launch_parser))

@pytest.mark.parametrize("suffix", [[], ["--unknown"], ["--slot", "unknown"], ["--transport", "unknown"]])
def test_launch_calls_canonical_validation(smoke: Any, tmp_path: Path, suffix: list[str]) -> None:
    argv, path = _launch_argv() + suffix, tmp_path / "argv.json"
    path.write_text(json.dumps(argv))
    validator = Mock(side_effect=_launch_parser)
    if suffix:
        with pytest.raises((ValueError, argparse.ArgumentError, SystemExit)):
            smoke.load_launch_argv(path, validator)
    else:
        assert smoke.load_launch_argv(path, validator) == argv
        with pytest.raises(ValueError):
            smoke.load_launch_argv(path, lambda _: False)
    validator.assert_called_once_with(argv)
@pytest.fixture()
def receipt() -> dict[str, Any]:
    requests = [dict(request_id=f"tv2safe-h2-{i}", model="gpt-6.1-sol", stream=False,
                     http_status=200, useful=True, attempted_backend="codex" if i < 12 else "droid",
                     trace_ref=f"trace:{i}") for i in range(20)]
    return dict(
        schema_version="1.0", run_id="l1-run", revision="r9", cab_base="a" * 40,
        skils_base="b" * 40, deployed_cab_sha="c" * 40, deployed_skils_sha="d" * 40,
        panel_proof_sha256="a" * 64, council_receipt_sha256="b" * 64,
        owner_authorization_ref="owner:l1", started_at_utc="2026-11-16T10:00:00Z",
        completed_at_utc="2026-11-16T10:01:00Z", hub_url="http://l1.invalid/v1",
        effective_config={"enabled_edges": ["codex", "droid"]},
        bridge_err_segments=[{"ref": "bridge.err:0:200", "inode": 1}], requests=requests,
        **{"H-0": {"status": "PASS"}, "H-2": {"n": 20, "codex_hits": 12, "droid_hits": 8},
           "H-2b": {"forced_edges": [
               dict(requests[i], request_id=f"tv2safe-h2b-{edge}", forced_backend=edge,
                    attempted_backend=edge, canonical_model="canonical", expected_canonical_model="canonical",
                    wire_owned_by=edge, expected_wire_owned_by=edge)
               for i, edge in enumerate(("codex", "droid"))], "codex_status": "PASS", "droid_status": "PASS"},
           "H-3": {"openai_key_2_hits": 0, "openai_key_3_hits": 0, "complete_coverage": True},
           "H-6": {"launch_rc": 0, "cli_fallback_rc": 0, "run_id": "l1-run", "receipt_ref": "launch:receipt"}},
        commands=[dict(argv=_launch_argv(), cwd="/l1", rc=0, stderr_ref="stderr:l1", crash_evidence_refs=[])],
        raw_logs=["sanitized:l1"], checks_tsv="checks:l1", status="PASS",
    )

@pytest.mark.parametrize("key,value", [
    ("H-2b", None), ("forced_edges", []), ("forced_edges", "codex,droid"),
    ("codex_status", None), ("droid_status", "NOT_RUN"), ("wrong_backend", None),
    ("one_edge", None), ("H-2", None), ("n", 19), ("codex_hits", 11), ("paid", 1),
    ("coverage", False), ("crash", ["SIGSEGV"]), ("schema_version", None),
    ("H-3", None), ("H-6", None), ("http_status", 500), ("useful", False),
    ("canonical_model", "wrong"), ("wire_owned_by", ""), ("expected_wire_owned_by", "wrong"),
])
def test_receipt_cannot_pass_without_h2_and_deterministic_h2b(
    smoke: Any, receipt: dict[str, Any], key: str, value: Any,
) -> None:
    assert smoke.validate_live_receipt(receipt) is True
    broken = copy.deepcopy(receipt)
    if key in {"H-2", "H-2b", "H-3", "H-6", "schema_version"}:
        del broken[key]
    elif key in {"n", "codex_hits"}:
        broken["H-2"][key] = value
    elif key in {"paid", "coverage"}:
        broken["H-3"]["openai_key_2_hits" if key == "paid" else "complete_coverage"] = value
    elif key == "crash":
        broken["commands"][0]["crash_evidence_refs"] = value
    elif key == "one_edge":
        broken["H-2b"]["forced_edges"].pop()
    elif key in {"http_status", "useful", "wrong_backend", "canonical_model", "wire_owned_by", "expected_wire_owned_by"}:
        broken["H-2b"]["forced_edges"][1]["attempted_backend" if key == "wrong_backend" else key] = value
    else:
        broken["H-2b"][key] = value
    assert smoke.validate_live_receipt(broken) is False
def _safe_writer(stream: Any, secret: str) -> Any:
    original = stream.write
    def write(data: Any) -> Any:
        assert secret not in str(data), "секрет передан файловому write"
        return original(data)
    stream.write = write
    return stream
@pytest.mark.parametrize("fail_replace", [False, True])
def test_receipt_is_masked_before_disk_stdout_and_atomically_replaced(
    smoke: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], fail_replace: bool,
) -> None:
    tmp_path = tmp_path / "receipts"
    tmp_path.mkdir()
    path, secret = tmp_path / "receipt.json", "synthetic-secret-c0-four"
    path.write_text('{"old":true}')
    data = {"schema_version": "1.0", "status": "BLOCKED", "api_key": secret,
            "detail": f"Bearer {secret}; api_key={secret}"}
    real_replace, real_open, real_io_open, real_fdopen = os.replace, builtins.open, io.open, os.fdopen
    replacements: list[bytes] = []
    def replace(source: Any, target: Any) -> None:
        assert Path(target) == path and Path(source).parent == path.parent and Path(source) != path
        assert json.loads(path.read_text()) == {"old": True}
        replacements.append(Path(source).read_bytes())
        if fail_replace:
            raise OSError("injected replace failure")
        real_replace(source, target)
    monkeypatch.setattr(builtins, "open", lambda *a, **k: _safe_writer(real_open(*a, **k), secret))
    monkeypatch.setattr(io, "open", lambda *a, **k: _safe_writer(real_io_open(*a, **k), secret))
    monkeypatch.setattr(os, "fdopen", lambda *a, **k: _safe_writer(real_fdopen(*a, **k), secret))
    monkeypatch.setattr(os, "replace", replace)
    if fail_replace:
        with pytest.raises(OSError, match="injected replace failure"):
            smoke.write_live_receipt(path, data)
        assert json.loads(path.read_text()) == {"old": True}
    else:
        smoke.write_live_receipt(path, data)
        assert json.loads(path.read_text())["status"] == "BLOCKED"
    assert len(replacements) == 1 and secret.encode() not in replacements[0]
    assert secret not in str(capsys.readouterr()) and list(tmp_path.iterdir()) == [path]
@pytest.mark.parametrize("bounds", BOUNDS, ids=[row[0] for row in BOUNDS])
@pytest.mark.parametrize("case", ["missing", "type", "text", "bool", "false", "nan", "inf", "-inf",
                                  "min-delta", "min", "mid", "max", "max+delta"])
def test_numeric_use_default_not_clamp(smoke: Any, bounds: tuple[str, float, float, float], case: str) -> None:
    name, default, low, high = bounds
    values = {"missing": None, "type": [], "text": "invalid", "bool": True, "false": False,
              "nan": "NaN", "inf": "Inf", "-inf": "-Inf", "min-delta": str(low - 0.001),
              "min": str(low), "mid": str((low + high) / 2), "max": str(high), "max+delta": str(high + 0.001)}
    assert smoke.parse_nfr_number(name, values[case]) == {"min": low, "mid": (low + high) / 2, "max": high}.get(case, default)
@pytest.mark.parametrize("failure", ["", "backend", "canonical", "owner", "body", "http", "mix", "secret", "logs", "logmissing", "logbackend", "logowner", "logcanonical"])
def test_h2_h2b_mocked_http(smoke: Any, monkeypatch: pytest.MonkeyPatch, failure: str, capsys: Any, tmp_path: Path) -> None:
    log = tmp_path / "bridge.err"
    calls: list[Any] = []
    def urlopen(request: Any, **kwargs: Any) -> Response:
        if request.get_method() == "GET":
            edge = request.full_url.split("/")[5]
            return Response(_body({"data": [{"id": {"codex": "gpt-6.1-sol-droid"}.get(edge, "canonical"), "owned_by": {"logowner": "wrong"}.get(failure, edge)}]}, JSON), JSON)
        calls.append(request)
        body = json.loads(request.data)
        assert body["stream"] is False
        assert request.get_header("Authorization") == "Bearer synthetic-l1"
        edge = ("codex" if len(calls) <= (11 if failure == "mix" else 12) else "droid") if len(calls) <= 20 else request.full_url.split("/")[5]
        response = Response(_body(_answer("quota exceeded" if failure == "body" else "PONG", "message"), JSON), JSON)
        response.headers["X-Attempted-Backend"] = {"backend": "wrong"}.get(failure, "wrong" if failure.startswith("log") else edge)
        response.headers["X-Canonical-Model"] = {"canonical": "wrong", "secret": "synthetic-l1", "logs": "wrong"}.get(failure, "canonical")
        response.headers["X-Wire-Owned-By"] = {"owner": ""}.get(failure, "" if failure.startswith("log") else edge)
        if failure.startswith("log"):
            log.write_text(f"passthrough route model={dict(logcanonical='wrong').get(failure, 'canonical')} backend={dict(logbackend='wrong').get(failure, edge)} request_id={dict(logmissing='unrelated').get(failure, request.get_header('X-request-id'))}\n")
        response.status = 500 if failure == "http" else 200
        return response
    monkeypatch.setattr(smoke.urllib.request, "urlopen", urlopen)
    argv = ["--live", "--run-id", "l1", "--owner-authorization-ref", "owner:l1",
            "--h2-model", "canonical", "--h2b-model", "gpt-6.1-sol-droid",
            "--h2b-canonical-model", "canonical", "--h2b-owned-by", "codex",
            "--h2b-peer-model", "canonical", "--h2b-peer-owned-by", "droid"]
    argv += ["--bridge-log", str(log)] if failure.startswith("log") else []
    assert smoke.main(argv + ["--dry-run"]) == 0 and not calls
    assert smoke.main(argv) == (0 if failure in ("", "logs") else 1)
    assert len(calls) == 22 and all("/v1/chat/completions" in call.full_url for call in calls) and "synthetic-l1" not in capsys.readouterr().out
def test_live_requires_authorization(smoke: Any) -> None:
    with pytest.raises(SystemExit):
        smoke.main(["--live", "--h2b-model", "l1-model"])

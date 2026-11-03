"""Детерминированные проверки QA-гейта, включая настоящий HTTP/SSE и CLI."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qa_product_gate_under_test", ROOT / "scripts/qa_product_gate.py"
)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def handoff(
    command: str = "pytest tests/ -v", code: Any = 0, purpose: str = "final"
) -> dict[str, Any]:
    return {
        "verification_commands": [
            {"command": command, "exit_code": code, "purpose": purpose}
        ]
    }


def test_incident_suite_replays_real_bridge() -> None:
    result = gate.run_incident_replay_suite()
    assert result["status"] == "PASS", result
    assert len(result["incidents"]) == 5
    assert result["incidents"]["wave_1a_prefix"]["steps"] >= 30
    assert result["incidents"]["wave_1a_prefix"]["divergences"] == 0
    assert all(item["status"] == "PASS" for item in result["incidents"].values())


def test_longer_replay_and_arbitrary_parser_fragmentation() -> None:
    result = gate.run_incident_replay_suite(
        gate.GateConfig(min_steps=60, parser_chunk_chars=1)
    )
    assert result["status"] == "PASS", result


def test_canaries_all_killed_and_restore_real_methods() -> None:
    srv = gate._bridge()
    from core import tool_emulation

    originals = (
        srv._ContentArbiter._scan,
        srv.Run.offer_content,
        srv._TranscriptTail.__init__,
        gate._reference_handoff,
        tool_emulation.sanitize_tool_calls_list,
    )
    result = gate.run_canary_sensitivity_gate()
    assert result["status"] == "PASS", result
    assert (result["total"], result["killed"], result["kill_rate"]) == (5, 5, 1.0)
    assert result["post_restore_green"] is True
    assert all(
        item["clean_green"] and item["killed"] and item["post_restore_green"]
        for item in result["canaries"]
    )
    assert originals == (
        srv._ContentArbiter._scan,
        srv.Run.offer_content,
        srv._TranscriptTail.__init__,
        gate._reference_handoff,
        tool_emulation.sanitize_tool_calls_list,
    )
    fifth = result["canaries"][4]
    assert fifth["name"] == "canary_5_tool_sanitizer_bypass"
    assert "error" not in fifth["mutated"]
    assert not fifth["mutated"]["checks"]["empty_optional_sanitized_payload_preserved"]
    assert not fifth["mutated"]["checks"]["case_3_indices"]
    assert gate.run_incident_replay_suite()["status"] == "PASS"


def test_ineffective_mutation_cannot_fake_sensitivity() -> None:
    with patch.object(
        gate,
        "_wave_boundary",
        return_value={"status": "PASS", "checks": {"no_glue": True}},
    ):
        result = gate.run_canary_sensitivity_gate()
    assert result["status"] == "FAIL"
    assert result["killed"] == 4
    assert result["kill_rate"] == 0.8


def test_broken_baseline_cannot_be_reported_as_canary_kill() -> None:
    with patch.object(
        gate, "_wave_boundary", side_effect=RuntimeError("broken baseline")
    ):
        result = gate.run_canary_sensitivity_gate()
    assert result["status"] == "FAIL"
    assert result["post_restore_green"] is False
    assert not result["canaries"][2]["killed"]


@pytest.mark.parametrize("code", [1, -1, 42, None, True, False, "0", 0.0])
def test_handoff_rejects_every_non_integer_zero(code: Any) -> None:
    assert gate.validate_handoff_commands(handoff(code=code))


@pytest.mark.parametrize(
    "command",
    [
        "pytest tests/ -k parser",
        "pytest tests/ -kparser",
        "pytest tests/ -m slow",
        "pytest tests/test_qa_product_gate.py -v",
        "pytest tests/test_qa_product_gate.py::test_incident_suite_replays_real_bridge",
        "pytest tests/ --ignore=tests/test_agy_bridge_resilience.py",
        "pytest tests/ --deselect=tests/test_qa_product_gate.py",
        "pytest tests/ --lf",
        "pytest tests/ --collect-only",
        "pytest tests/ -o python_files=nothing",
        "pytest tests/ -c alternate.ini",
        "pytest other/",
        "pytest tests/ other/test_one.py::test_one",
        "pytest tests/ --confcutdir=other",
        "pytest tests/ --setup-on",
        "echo pytest tests/",
        "pytest tests/ || true",
        "pytest tests/; echo ok",
        "pytest tests/ > output",
        "pytest tests/ -k 'unterminated",
        "python -c 'pytest tests/'",
    ],
)
def test_final_handoff_rejects_selective_or_forged_commands(command: str) -> None:
    assert gate.run_sdlc_integrity_check(handoff(command))["status"] == "FAIL"


@pytest.mark.parametrize(
    "flag",
    [
        "--setup-only",
        "--setup-plan",
        "--setup-show",
        "--fixtures",
        "--fixtures-per-test",
        "--markers",
        "--version",
        "--help",
        "-h",
        "--cache-show",
        "--cache-show=*",
        "-V",
        "--collect-only",
        "--co",
    ],
)
def test_nonexecuting_pytest_flags_never_count_as_execution(flag: str) -> None:
    payload = handoff(f"pytest tests/ {flag}")
    assert gate.validate_handoff_commands(payload)
    payload["verification_commands"].extend(handoff()["verification_commands"])
    assert gate.validate_handoff_commands(payload)
    assert gate.validate_handoff_commands(payload, final_readiness=False)


@pytest.mark.parametrize(
    "command",
    [
        "pytest",
        "pytest -q",
        "pytest tests/",
        "pytest .",
        "pytest ./tests/ -v",
        "python3 -m pytest tests/ -v",
        "uv run pytest tests/ -q",
        "run-guarded -- python3 -m pytest tests/ -v",
    ],
)
def test_final_handoff_accepts_full_coverage(command: str) -> None:
    assert gate.validate_handoff_commands(handoff(command)) == []


def test_required_tests_are_only_an_explicit_subset() -> None:
    payload = handoff("pytest " + " ".join(sorted(gate.REQUIRED_TESTS)) + " -v")
    assert gate.validate_handoff_commands(payload)
    assert not gate.validate_handoff_commands(payload, allow_gate_subset=True)
    assert gate._reference_handoff()["verification_commands"][0]["command"] == (
        "pytest tests/ -v"
    )


def test_default_purpose_is_final() -> None:
    payload = handoff()
    del payload["verification_commands"][0]["purpose"]
    assert not gate.validate_handoff_commands(payload)


@pytest.mark.parametrize("code", [0, -1, None, True, False, "1", 1.0])
def test_red_repro_requires_positive_integer(code: Any) -> None:
    assert gate.validate_handoff_commands(
        handoff(code=code, purpose="red_repro"), final_readiness=False
    )


def test_red_repro_and_diagnostic_do_not_replace_final_suite() -> None:
    red = handoff("pytest tests/test_qa_product_gate.py -k regression", 1, "red_repro")
    diagnostic = handoff("ruff check .", 1, "diagnostic")
    assert not gate.validate_handoff_commands(red, final_readiness=False)
    assert not gate.validate_handoff_commands(diagnostic, final_readiness=False)
    assert gate.validate_handoff_commands(red)
    assert gate.validate_handoff_commands(diagnostic)
    payload = handoff()
    payload["verification_commands"].extend(red["verification_commands"])
    payload["verification_commands"].extend(diagnostic["verification_commands"])
    assert not gate.validate_handoff_commands(payload)


@pytest.mark.parametrize("purpose", ["unknown", "", "FINAL"])
def test_unknown_purpose_fails(purpose: str) -> None:
    assert gate.validate_handoff_commands(
        handoff(purpose=purpose), final_readiness=False
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"verification_commands": []},
        {"verification_commands": [None]},
        {"verification_commands": [{"exit_code": 0}]},
        handoff("ruff check ."),
    ],
)
def test_handoff_rejects_malformed_or_missing_verification(payload: Any) -> None:
    assert gate.run_sdlc_integrity_check(payload)["status"] == "FAIL"


def test_partial_checks_can_be_validated_without_final_readiness_claim() -> None:
    assert not gate.validate_handoff_commands(
        handoff("pytest tests/test_qa_product_gate.py"), final_readiness=False
    )
    assert gate.run_sdlc_integrity_check()["scope"] == "validator_self_test"


def frame(delta: dict[str, Any], finish: str | None = None) -> str:
    return (
        "data: "
        + json.dumps(
            {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        )
        + "\n\n"
    )


VALID_STREAM = (
    frame({"content": "QA-47: контекст сохранён."})
    + frame({}, "stop")
    + "data: [DONE]\n\n"
)


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    state: dict[str, Any] = {
        "stream": VALID_STREAM,
        "models": {"data": [{"id": "local-qa-model"}]},
        "requests": [],
        "log": tmp_path / "bridge.err",
    }
    state["log"].write_text("", encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            state["requests"].append((self.path, dict(self.headers), None))
            if state.get("get_delay"):
                time.sleep(state["get_delay"])
            status = (
                state.get("health_status", 200)
                if self.path == "/health"
                else state.get("models_status", 200)
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                if self.path == "/health" and state.get("plain_health"):
                    self.wfile.write(b"OK")
                    return
                self.wfile.write(
                    json.dumps(
                        {"status": "ok"} if self.path == "/health" else state["models"]
                    ).encode()
                )
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self) -> None:
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, dict(self.headers), data))
            if state.get("keep_alive"):
                self.protocol_version = "HTTP/1.1"
                self.close_connection = False
            self.send_response(state.get("stream_status", 200))
            self.send_header(
                "Content-Type", state.get("content_type", "text/event-stream")
            )
            if state.get("keep_alive"):
                self.send_header(
                    "Content-Length", str(len(state["stream"].encode()) + 10)
                )
            self.end_headers()
            if state.get("rotate_log"):
                state["log"].rename(state["log"].with_suffix(".old"))
                state["log"].write_text("", encoding="utf-8")
            if state.get("truncate_log"):
                state["log"].write_text("", encoding="utf-8")
            if state.get("overwrite_log"):
                state["log"].write_text(state["overwrite_log"], encoding="utf-8")
            if state.get("append_log"):
                with state["log"].open("a", encoding="utf-8") as log:
                    log.write(state["append_log"])
            try:
                if state.get("slow_stream"):
                    for byte in state["stream"].encode():
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.02)
                else:
                    self.wfile.write(state["stream"].encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def hub_config(state: dict[str, Any]) -> Any:
    return gate.GateConfig(
        live_timeout_s=2, live_total_timeout_s=5, log_path=state["log"]
    )


def test_live_hub_multiturn_protocol_headers_and_model(
    hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    url, state = hub
    monkeypatch.setenv("QA_GATE_API_KEY", "private-test-token")
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "PASS", result
    assert result["log_inspection"]["status"] == "PASS"
    requests = state["requests"]
    assert [item[0] for item in requests] == [
        "/health",
        "/v1/models",
        "/v1/chat/completions",
    ]
    _, headers, payload = requests[-1]
    assert headers["X-Subagent-Id"] == "qa-product-gate-probe"
    assert headers["Authorization"] == "Bearer private-test-token"
    assert [m["role"] for m in payload["messages"]] == ["user", "assistant", "user"]
    assert payload["stream"] is True
    assert payload["model"] == "local-qa-model"
    assert "private-test-token" not in json.dumps(result)


def test_missing_log_is_a_blocking_failure(hub: Any) -> None:
    url, state = hub
    state["log"].unlink()
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    assert result["log_inspection"]["status"] == "UNAVAILABLE"
    assert result["checks"]["no_new_5xx_or_traceback"] is False


def test_log_created_during_probe_does_not_restore_observability(hub: Any) -> None:
    url, state = hub
    state["log"].unlink()
    state["append_log"] = "healthy\n"
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    assert result["log_inspection"]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("mode", ["rotate_log", "truncate_log"])
def test_rotation_and_truncation_fail_closed(hub: Any, mode: str) -> None:
    url, state = hub
    state["log"].write_text("old log line\n", encoding="utf-8")
    state[mode] = True
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    assert result["log_inspection"]["rotated_or_truncated"] is True
    assert result["log_inspection"]["complete"] is False


def test_same_inode_truncate_and_regrow_fails_closed(hub: Any) -> None:
    url, state = hub
    state["log"].write_text("initial_prefix_12345\n", encoding="utf-8")
    before = state["log"].stat()
    state["overwrite_log"] = "rewritten_prefix_12345_and_longer_tail\n"
    result = gate.run_live_hub_probe(url, hub_config(state))
    after = state["log"].stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
    assert after.st_size > before.st_size
    assert result["status"] == "FAIL"
    assert result["log_inspection"]["rotated_or_truncated"] is True
    assert result["log_inspection"]["complete"] is False


def test_content_divergence_fails_log_hygiene(hub: Any) -> None:
    url, state = hub
    state["append_log"] = "warning: content-divergence detected\n"
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    assert result["log_inspection"]["new_errors"] == [
        "warning: content-divergence detected"
    ]


def test_error_marker_detected_before_redaction(
    hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    url, state = hub
    monkeypatch.setenv("QA_GATE_API_KEY", "private-test-token")
    state["append_log"] = "token=content-divergence\n"
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    assert result["checks"]["no_new_5xx_or_traceback"] is False
    assert result["log_inspection"]["new_errors"]
    assert "content-divergence" not in json.dumps(
        result["log_inspection"]["new_errors"]
    )

    monkeypatch.setenv("QA_GATE_API_KEY", "Traceback")
    state["append_log"] = "Traceback\n"
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    assert result["checks"]["no_new_5xx_or_traceback"] is False
    assert result["log_inspection"]["new_errors"] == ["[REDACTED]"]


def test_bridge_key_from_environment(hub: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    url, state = hub
    monkeypatch.delenv("QA_GATE_API_KEY", raising=False)
    monkeypatch.setenv("BRIDGE_KEY", "bridge-env-token")
    assert gate.run_live_hub_probe(url, hub_config(state))["status"] == "PASS"
    assert state["requests"][-1][1]["Authorization"] == "Bearer bridge-env-token"


def test_bridge_key_from_dotenv_and_redaction(
    hub: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url, state = hub
    monkeypatch.delenv("QA_GATE_API_KEY", raising=False)
    monkeypatch.delenv("BRIDGE_KEY", raising=False)
    home = tmp_path / "home"
    (home / ".dsh").mkdir(parents=True)
    (home / ".dsh" / ".env").write_text(
        '# local configuration\nBRIDGE_KEY="dotenv-private-token"\n',
        encoding="utf-8",
    )
    with patch.object(gate.Path, "home", return_value=home):
        result = gate.run_live_hub_probe(url, hub_config(state))
        assert result["status"] == "PASS"
        state["append_log"] = "Traceback dotenv-private-token\n"
        result = gate.run_live_hub_probe(url, hub_config(state))
    assert state["requests"][-1][1]["Authorization"] == "Bearer dotenv-private-token"
    assert result["status"] == "FAIL"
    assert "dotenv-private-token" not in json.dumps(result)


def test_live_done_does_not_wait_for_socket_eof(hub: Any) -> None:
    url, state = hub
    state.update(keep_alive=True, plain_health=True)
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "PASS", result


def test_shared_deadline_limits_all_urlopen_calls(hub: Any) -> None:
    url, state = hub
    state["get_delay"] = 0.04
    real_urlopen = gate.urlopen
    timeouts: list[float] = []

    def recording_open(request: Any, *, timeout: float) -> Any:
        timeouts.append(timeout)
        return real_urlopen(request, timeout=timeout)

    config = replace(hub_config(state), live_timeout_s=10, live_total_timeout_s=2)
    with patch.object(gate, "urlopen", side_effect=recording_open):
        result = gate.run_live_hub_probe(url, config)
    assert result["status"] == "PASS", result
    assert len(timeouts) == 3
    assert 0 < timeouts[2] < timeouts[1] < timeouts[0] <= 2


@pytest.mark.parametrize("slow_phase", ["get_delay", "slow_stream"])
def test_live_total_budget_covers_get_and_partial_lines(
    hub: Any, slow_phase: str
) -> None:
    url, state = hub
    state[slow_phase] = 0.5 if slow_phase == "get_delay" else True
    config = replace(hub_config(state), live_timeout_s=2, live_total_timeout_s=0.2)
    started = time.monotonic()
    result = gate.run_live_hub_probe(url, config)
    elapsed = time.monotonic() - started
    assert result["status"] == "FAIL"
    assert elapsed < 1.5


def test_static_sse_rejects_data_after_done() -> None:
    with pytest.raises(ValueError, match="framing"):
        gate._parse_sse(
            (VALID_STREAM + frame({"content": "late"})).splitlines(True),
            gate.GateConfig(),
        )


def test_sse_accepts_final_content_and_stop_in_same_chunk() -> None:
    frames = gate._parse_sse(
        (frame({"content": "QA-47"}, "stop") + "data: [DONE]\n\n").splitlines(True),
        gate.GateConfig(),
    )
    assert gate._channel(frames, "content") == "QA-47"


@pytest.mark.parametrize(
    "change",
    [
        {"health_status": 503},
        {"models_status": 500},
        {"models": {"data": []}},
        {"models": {"data": [{"id": ""}]}},
        {"stream_status": 502},
        {"content_type": "application/json"},
        {"stream": "garbage\n\n"},
        {"stream": frame({"content": "QA-47"})},
        {
            "stream": frame({"content": "QA-47"})
            + frame({}, "length")
            + "data: [DONE]\n\n"
        },
        {"stream": frame({}, "stop") + "data: [DONE]\n\n"},
        {"stream": "data: [DONE]\n\n"},
        {"stream": "data: {oops}\n\n"},
        {"stream": frame({"content": "QA-47"}) + frame({}, "stop") + "data: [DONE]\n"},
        {
            "stream": frame({"content": "ответ без контекста"})
            + frame({}, "stop")
            + "data: [DONE]\n\n"
        },
        {"stream": "data: " + json.dumps({"error": "sk-secret-value"}) + "\n\n"},
    ],
)
def test_live_probe_fails_closed(hub: Any, change: dict[str, Any]) -> None:
    url, state = hub
    state.update(change)
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL", result
    assert "sk-secret-value" not in json.dumps(result)


def test_live_log_delta_ignores_old_errors_and_redacts_new(hub: Any) -> None:
    url, state = hub
    state["log"].write_text("old Traceback 502 sk-old-token\n", encoding="utf-8")
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "PASS"
    assert result["log_inspection"]["new_bytes"] == 0
    state["append_log"] = (
        "Traceback 503 sk-test-new-token Authorization: Bearer very-secret-value\n"
    )
    result = gate.run_live_hub_probe(url, hub_config(state))
    assert result["status"] == "FAIL"
    rendered = json.dumps(result)
    assert "sk-test-new-token" not in rendered
    assert "very-secret-value" not in rendered
    assert "REDACTED" in rendered


def test_large_log_delta_cannot_claim_clean_tail(hub: Any) -> None:
    url, state = hub
    state["append_log"] = "Traceback\n" + "x" * 512
    result = gate.run_live_hub_probe(url, replace(hub_config(state), log_tail_bytes=32))
    assert result["status"] == "FAIL"
    assert result["log_inspection"]["complete"] is False


def test_live_bounds_response_and_line_sizes(hub: Any) -> None:
    url, state = hub
    state["stream"] = (
        frame({"content": "QA-47" * 100}) + frame({}, "stop") + "data: [DONE]\n\n"
    )
    for changes in ({"max_response_bytes": 256}, {"max_sse_line_bytes": 128}):
        assert (
            gate.run_live_hub_probe(url, replace(hub_config(state), **changes))[
                "status"
            ]
            == "FAIL"
        )


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/a",
        "http://user:password@localhost/v1",
        "http://localhost/v1?token=secret",
        "nonsense",
    ],
)
def test_probe_rejects_invalid_url(url: str) -> None:
    assert gate.run_live_hub_probe(url)["status"] == "FAIL"


def test_config_from_env_and_invalid_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_GATE_MIN_STEPS", "45")
    monkeypatch.setenv("QA_GATE_MODEL", "configured-model")
    monkeypatch.setenv("QA_GATE_LIVE_TIMEOUT_S", "3.5")
    monkeypatch.setenv("QA_GATE_WORKTREE_FINGERPRINT", "snapshot-45")
    monkeypatch.setenv("QA_GATE_GIT_TIMEOUT_S", "2.5")
    monkeypatch.setenv("QA_GATE_READ_CHUNK_BYTES", "1024")
    monkeypatch.setenv("QA_GATE_MIN_CANARY_TOTAL", "6")
    monkeypatch.setenv("QA_GATE_LOG_ERROR_PATTERN", r" custom-error|\b599\b ")
    cfg = gate.GateConfig.from_env()
    assert (cfg.min_steps, cfg.model, cfg.live_timeout_s) == (
        45,
        "configured-model",
        3.5,
    )
    assert cfg.worktree_fingerprint == "snapshot-45"
    assert (cfg.git_timeout_s, cfg.read_chunk_bytes, cfg.min_canary_total) == (
        2.5,
        1024,
        6,
    )
    assert cfg.log_error_pattern == r"custom-error|\b599\b"
    monkeypatch.setenv("QA_GATE_LOG_ERROR_PATTERN", " ")
    assert (
        gate.GateConfig.from_env().log_error_pattern
        == gate.GateConfig.log_error_pattern
    )
    for value in ("29", "0", "-1", "nan", "inf", "1.5", "oops"):
        monkeypatch.setenv("QA_GATE_MIN_STEPS", value)
        with pytest.raises(ValueError):
            gate.GateConfig.from_env()


def valid_proof() -> dict[str, Any]:
    return gate.build_proof(
        {
            "G1": {"status": "PASS"},
            "G2": {"status": "PASS", "scope": "provided_handoff"},
            "G3": {"status": "PASS", "total": 5, "killed": 5, "kill_rate": 1.0},
        },
        worktree_fingerprint="snapshot-current",
    )


def write_proof(path: Path, proof: dict[str, Any], *, rehash: bool = True) -> None:
    if rehash:
        proof["sha256"] = gate._proof_checksum(proof)
    path.write_text(json.dumps(proof, ensure_ascii=False), encoding="utf-8")


def test_proof_hash_is_canonical_and_deterministic() -> None:
    data = {"G2": gate.run_sdlc_integrity_check()}
    first = gate.build_proof(data, worktree_fingerprint="fixed")
    assert first == gate.build_proof(data, worktree_fingerprint="fixed")
    digest = first.pop("sha256")
    assert (
        digest
        == hashlib.sha256(
            json.dumps(
                first,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )


def test_default_fingerprint_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_GATE_WORKTREE_FINGERPRINT", "environment-snapshot")
    result = gate.build_proof({"G1": {"status": "PASS"}})
    assert result["worktree_fingerprint"] == "environment-snapshot"


def test_fingerprint_git_inputs_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QA_GATE_WORKTREE_FINGERPRINT", raising=False)
    monkeypatch.setenv("QA_GATE_GIT_TIMEOUT_S", "2.5")
    outputs = [
        subprocess.CompletedProcess([], 0, stdout=b"head\n"),
        subprocess.CompletedProcess([], 0, stdout=b" M tracked.py\n"),
    ]
    with patch.object(gate.subprocess, "run", side_effect=outputs) as run:
        result = gate.build_proof({"G1": {"status": "PASS"}})
    assert (
        result["worktree_fingerprint"]
        == hashlib.sha256(b"head\n\0 M tracked.py\n").hexdigest()
    )
    assert run.call_args_list[0].args[0] == ["git", "rev-parse", "HEAD"]
    assert run.call_args_list[1].args[0] == ["git", "status", "--porcelain"]
    assert all(call.kwargs["timeout"] == 2.5 for call in run.call_args_list)
    with patch.object(gate.subprocess, "run", side_effect=outputs) as run:
        gate._worktree_fingerprint(gate.GateConfig(git_timeout_s=1.5))
    assert all(call.kwargs["timeout"] == 1.5 for call in run.call_args_list)
    with patch.object(gate.subprocess, "run", side_effect=OSError("git missing")):
        result = gate.build_proof({"G1": {"status": "PASS"}})
    assert result["overall_status"] == "FAIL"
    assert result["worktree_fingerprint"] == ""


def test_verify_proof_contract_accepts_valid_proof(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    write_proof(path, valid_proof())
    assert (
        gate.verify_proof_contract(path, expected_fingerprint="snapshot-current") == []
    )


def test_verify_proof_contract_requires_expected_fingerprint_by_default(
    tmp_path: Path,
) -> None:
    path = tmp_path / "proof.json"
    write_proof(path, valid_proof())
    assert gate.verify_proof_contract(path) == ["expected_fingerprint обязателен"]
    for fingerprint in ("", " "):
        assert gate.verify_proof_contract(path, expected_fingerprint=fingerprint) == [
            "expected_fingerprint обязателен"
        ]
    assert gate.verify_proof_contract(path, allow_unbound=True) == []
    assert gate.verify_proof_contract(
        path, expected_fingerprint="stale-snapshot", allow_unbound=True
    ) == ["worktree_fingerprint не совпадает с ожидаемым"]


def test_missing_unreadable_and_malformed_proof_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")
    assert gate.verify_proof_contract(tmp_path, expected_fingerprint="snapshot-current")
    for raw in ("not json", "null", "[]", '{"a":1,"a":2}', '{"a":NaN}'):
        path.write_text(raw, encoding="utf-8")
        assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")
    with patch.object(gate.Path, "read_text", side_effect=PermissionError("denied")):
        assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")


def test_stale_fingerprint_blocks_transition(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    write_proof(path, valid_proof())
    errors = gate.verify_proof_contract(path, expected_fingerprint="new-snapshot")
    assert any("fingerprint" in error for error in errors)


@pytest.mark.parametrize("name", ["G1", "G2", "G3"])
def test_missing_or_failed_required_gate_blocks_transition(
    tmp_path: Path, name: str
) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    del proof["gates"][name]
    write_proof(path, proof)
    assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")
    proof = valid_proof()
    proof["gates"][name]["status"] = "FAIL"
    write_proof(path, proof)
    assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")


def test_required_live_gate_can_be_enforced(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    write_proof(path, proof)
    assert gate.verify_proof_contract(
        path,
        expected_fingerprint="snapshot-current",
        required_gates=("G1", "G2", "G3", "G4"),
    )
    proof["gates"]["G4"] = {"status": "PASS"}
    write_proof(path, proof)
    assert not gate.verify_proof_contract(
        path,
        expected_fingerprint="snapshot-current",
        required_gates=("G1", "G2", "G3", "G4"),
    )


def test_self_test_scope_does_not_authorize_fsm(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    proof["gates"]["G2"]["scope"] = "validator_self_test"
    write_proof(path, proof)
    assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")
    assert not gate.verify_proof_contract(
        path,
        expected_fingerprint="snapshot-current",
        require_provided_handoff=False,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2.0"),
        ("overall_status", "FAIL"),
        ("worktree_fingerprint", ""),
        ("worktree_fingerprint", None),
        ("gates", []),
        ("canary_sensitivity", None),
    ],
)
def test_invalid_proof_structure_blocks_transition(
    tmp_path: Path, field: str, value: Any
) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    proof[field] = value
    write_proof(path, proof)
    assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kill_rate", 0.8),
        ("kill_rate", True),
        ("kill_rate", "1.0"),
        ("total", 4),
        ("total", True),
        ("total", 5.0),
        ("killed", 4),
    ],
)
def test_invalid_canary_sensitivity_blocks_transition(
    tmp_path: Path, field: str, value: Any
) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    proof["canary_sensitivity"][field] = value
    write_proof(path, proof)
    assert gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")


@pytest.mark.parametrize(
    ("field", "value"),
    [("total", 6), ("killed", 4), ("kill_rate", 0.8)],
)
def test_verify_proof_contract_rejects_g3_inconsistency(
    tmp_path: Path, field: str, value: Any
) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    proof["gates"]["G3"][field] = value
    write_proof(path, proof)
    assert gate.verify_proof_contract(
        path, expected_fingerprint="snapshot-current"
    ) == ["canary_sensitivity не согласован с G3"]


def test_verify_proof_contract_configurable_min_canary_total(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    write_proof(path, valid_proof())
    assert gate.verify_proof_contract(
        path, expected_fingerprint="snapshot-current", min_canary_total=6
    ) == ["canary_sensitivity.total должен быть целым >= 6"]


def test_min_canary_total_enforced_in_g3_cli_and_fsm_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QA_GATE_MIN_CANARY_TOTAL", "6")
    assert gate.run_canary_sensitivity_gate()["status"] == "FAIL"
    proof = tmp_path / "qa-gate-proof.json"
    assert gate.main(["--all", "--output-proof", str(proof)]) == 1
    data = json.loads(proof.read_text())
    assert data["overall_status"] == "FAIL"
    assert data["gates"]["G3"]["status"] == "FAIL"
    write_proof(proof, valid_proof())
    assert gate.verify_fsm_transition(
        tmp_path,
        {"schema_version": 2, "worktree_fingerprint": "snapshot-current"},
    ) == ["canary_sensitivity.total должен быть целым >= 6"]
    capsys.readouterr()


@pytest.mark.parametrize("live_required", [False, True])
def test_verify_fsm_transition_enforces_schema_v2_and_calls_verifier(
    tmp_path: Path, live_required: bool
) -> None:
    state: dict[str, Any] = {
        "schema_version": "2",
        "qa_gate_required": False,
        "live_gate_required": live_required,
    }
    with patch.object(
        gate, "verify_proof_contract", return_value=["verifier failure"]
    ) as verifier:
        assert (
            gate.verify_fsm_transition(
                tmp_path, {"schema_version": 1, "qa_gate_required": False}
            )
            == []
        )
        verifier.assert_not_called()
        for bad_ver in (True, False, 0, -1, 1.5, float("inf"), "v2", None):
            assert gate.verify_fsm_transition(
                tmp_path,
                {
                    "schema_version": bad_ver,
                    "qa_gate_required": False,
                    "worktree_fingerprint": "snapshot-current",
                },
            ) == ["невалидный state.schema_version"]
        verifier.assert_not_called()
        assert gate.verify_fsm_transition(tmp_path, state) == [
            "отсутствует доверенный state.worktree_fingerprint"
        ]
        verifier.assert_not_called()
        for fingerprint in ("", " ", 123):
            state["worktree_fingerprint"] = fingerprint
            assert gate.verify_fsm_transition(tmp_path, state) == [
                "отсутствует доверенный state.worktree_fingerprint"
            ]
        verifier.assert_not_called()
        state["worktree_fingerprint"] = "snapshot-current"
        assert gate.verify_fsm_transition(tmp_path, state) == ["verifier failure"]
        verifier.assert_called_once_with(
            tmp_path / "qa-gate-proof.json",
            expected_fingerprint="snapshot-current",
            require_provided_handoff=True,
            required_gates=(
                ("G1", "G2", "G3", "G4") if live_required else ("G1", "G2", "G3")
            ),
            min_canary_total=gate.GateConfig.from_env().min_canary_total,
        )


@pytest.mark.parametrize("schema_version", [None, "invalid", [], {}])
def test_verify_fsm_transition_rejects_invalid_schema_version(
    tmp_path: Path, schema_version: Any
) -> None:
    assert gate.verify_fsm_transition(tmp_path, {"schema_version": schema_version}) == [
        "невалидный state.schema_version"
    ]


def test_verify_fsm_transition_rejects_invalid_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QA_GATE_MIN_CANARY_TOTAL", "invalid")
    assert gate.verify_fsm_transition(
        tmp_path,
        {"schema_version": 2, "worktree_fingerprint": "snapshot-current"},
    ) == ["невалидная конфигурация окружения QA-гейта"]


def test_checksum_tampering_blocks_transition(tmp_path: Path) -> None:
    path = tmp_path / "proof.json"
    proof = valid_proof()
    proof["worktree_fingerprint"] = "modified"
    write_proof(path, proof, rehash=False)
    errors = gate.verify_proof_contract(path, expected_fingerprint="snapshot-current")
    assert any("sha256" in error for error in errors)


def test_cli_all_proof_and_return_code(tmp_path: Path) -> None:
    proof = tmp_path / "qa-gate-proof.json"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/qa_product_gate.py"),
            "--all",
            "--output-proof",
            str(proof),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    data = json.loads(proof.read_text())
    assert data == json.loads(process.stdout)
    assert data["schema_version"] == "1.0"
    assert data["overall_status"] == "PASS"
    assert set(data["gates"]) == {"G1", "G2", "G3"}
    assert data["canary_sensitivity"] == {"total": 5, "killed": 5, "kill_rate": 1.0}
    assert data["worktree_fingerprint"]
    assert gate.verify_proof_contract(proof, allow_unbound=True)
    assert not gate.verify_proof_contract(
        proof, allow_unbound=True, require_provided_handoff=False
    )


def test_cli_live_includes_g4(
    hub: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, state = hub
    monkeypatch.setenv("QA_GATE_LOG_PATH", str(state["log"]))
    proof = tmp_path / "proof.json"
    assert gate.main(["--all", "--live-hub", url, "--output-proof", str(proof)]) == 0
    assert set(json.loads(proof.read_text())["gates"]) == {"G1", "G2", "G3", "G4"}
    assert json.loads(capsys.readouterr().out)["overall_status"] == "PASS"


def test_cli_provided_handoff_passes_blocking_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "handoff.json"
    source.write_text(json.dumps(handoff()), encoding="utf-8")
    proof = tmp_path / "proof.json"
    monkeypatch.setenv("QA_GATE_WORKTREE_FINGERPRINT", "orchestrator-snapshot")
    assert (
        gate.main(
            [
                "--all",
                "--handoff",
                str(source),
                "--output-proof",
                str(proof),
            ]
        )
        == 0
    )
    assert not gate.verify_proof_contract(
        proof, expected_fingerprint="orchestrator-snapshot"
    )
    capsys.readouterr()


@pytest.mark.parametrize(
    "raw",
    [
        "null",
        "not json",
        '{"verification_commands":[{"command":"pytest tests/","exit_code":1}]}',
    ],
)
def test_cli_invalid_handoff_is_fail(
    tmp_path: Path, raw: str, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "handoff.json"
    source.write_text(raw, encoding="utf-8")
    proof = tmp_path / "proof.json"
    assert gate.main(["--handoff", str(source), "--output-proof", str(proof)]) == 1
    assert json.loads(proof.read_text())["overall_status"] == "FAIL"
    assert gate.verify_proof_contract(proof, allow_unbound=True)
    capsys.readouterr()


@pytest.mark.parametrize(
    "env_name", ["QA_GATE_LIVE_TIMEOUT_S", "QA_GATE_GIT_TIMEOUT_S"]
)
def test_cli_invalid_config_writes_fail_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    env_name: str,
) -> None:
    monkeypatch.delenv("QA_GATE_WORKTREE_FINGERPRINT", raising=False)
    monkeypatch.setenv(env_name, "nan")
    proof = tmp_path / "proof.json"
    assert gate.main(["--all", "--output-proof", str(proof)]) == 1
    assert json.loads(proof.read_text())["overall_status"] == "FAIL"
    assert gate.verify_proof_contract(proof, allow_unbound=True)
    capsys.readouterr()


def test_patched_spec_loader_and_entry_points_in_fresh_subprocess(
    tmp_path: Path,
) -> None:
    write_proof(tmp_path / "qa-gate-proof.json", valid_proof())
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "qa_product_gate", Path.cwd() / "scripts" / "qa_product_gate.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

tmp_path = Path(sys.argv[1])
valid_handoff = json.loads(sys.argv[2])
invalid_handoff = dict(valid_handoff)
invalid_handoff["verification_commands"] = [
    {"command": "pytest tests/", "exit_code": 1}
]
assert mod.validate_handoff_commands(valid_handoff, final_readiness=True) == []
assert mod.validate_handoff_commands(invalid_handoff, final_readiness=True)

valid_state = {
    "schema_version": 2,
    "worktree_fingerprint": "snapshot-current",
}
invalid_state = {
    "schema_version": True,
    "qa_gate_required": False,
    "worktree_fingerprint": "snapshot-current",
}
assert mod.verify_fsm_transition(tmp_path, valid_state) == []
assert mod.verify_fsm_transition(tmp_path, invalid_state)
""",
            str(tmp_path),
            json.dumps(handoff()),
        ],
        cwd=ROOT,
        check=True,
    )

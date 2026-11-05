from __future__ import annotations

from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from typing import Any

import pytest

import scripts.smoke_models as smoke_models_module
from scripts.smoke_models import (
    DEFAULT_MODEL_NOTES_MD,
    DEFAULT_MODELS_MD,
    ModelEntry,
    ModelLimitException,
    build_bridge_payload,
    deduplicate_models_for_parallel,
    is_model_limit_error,
    parse_models_md,
    parse_temp_off_models,
    run_parallel_smoke,
    smoke_test_model,
)


FALLBACK_ENTRIES = [
    ModelEntry("Coder", "claude-sonnet-5-5", "high", "Anthropic"),
    ModelEntry("Coder", "gpt-6.1-sol", "high", "OpenAI"),
    ModelEntry("Coder", "gemini-4-argon-high", "high", "Google"),
    ModelEntry("Coder", "muse-wonder-full-1.0", "high", "Meta"),
    ModelEntry("Reviewer", "gpt-6.1-sol", "medium", "OpenAI"),
    ModelEntry("Brief-review", "gemini-3.8-flash-medium", "medium", "Google"),
    ModelEntry("Brief-review", "claude-haiku-5-5", "medium", "Anthropic"),
    ModelEntry("Answer review", "deepseek-v4.1-flash", "off", "DeepSeek"),
]


def _write_models_fixture(path: Path) -> Path:
    path.write_text(
        """# Models

### Coder

| Модель | Effort | Family |
| --- | --- | --- |
| `claude-sonnet-5-5` | `high` | Anthropic |
| `gpt-6.1-sol` | `high` | OpenAI |
| `gemini-4-argon-high` | `high` | Google |
| `muse-wonder-full-1.0` | `high` | Meta |

### Reviewer

| Модель | Effort | Family |
| --- | --- | --- |
| `gpt-6.1-sol` | `medium` | OpenAI |

### Brief-review

| Модель | Effort | Family |
| --- | --- | --- |
| `gemini-3.8-flash-medium` | `medium` | Google |
| `claude-haiku-5-5` | `medium` | Anthropic |

### Answer review

| Модель | Effort | Family |
| --- | --- | --- |
| `deepseek-v4.1-flash` | `off` | DeepSeek |
""",
        encoding="utf-8",
    )
    return path


def _load_entries(path: Path) -> list[ModelEntry]:
    return deduplicate_models_for_parallel(parse_models_md(path))


class MockBridgeState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.current_in_flight = 0
        self.max_in_flight = 0
        self.records: list[dict[str, Any]] = []
        self.behaviors: dict[str, int] = {}


class _HighBacklogHTTPServer(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


class MockBridge(AbstractContextManager["MockBridge"]):
    def __init__(self) -> None:
        self.state = MockBridgeState()
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, format: str, *args: Any) -> None:
                return

            def do_POST(self) -> None:
                if not self.path.endswith("/chat/completions"):
                    self.send_error(404)
                    return

                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                body = json.loads(raw_body.decode("utf-8"))
                record = {
                    "subagent_id": self.headers.get("X-Subagent-Id"),
                    "authorization": self.headers.get("Authorization"),
                    "body": body,
                }

                with state.lock:
                    state.records.append(record)
                    state.current_in_flight += 1
                    state.max_in_flight = max(
                        state.max_in_flight, state.current_in_flight
                    )

                try:
                    time.sleep(0.25)
                    model = body.get("model", "")
                    response_status = state.behaviors.get(model, 200)
                    if response_status == 429:
                        payload = {
                            "error": {
                                "message": "quota_exceeded / model_cooldown",
                                "type": "rate_limit_error",
                            }
                        }
                        encoded = json.dumps(payload).encode("utf-8")
                        self.send_response(429)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return
                    if response_status == 500:
                        message = (
                            "connection pool exhausted"
                            if model == "pool-failure-model"
                            else "ordinary bridge failure"
                        )
                        payload = {"error": {"message": message}}
                        encoded = json.dumps(payload).encode("utf-8")
                        self.send_response(500)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    if model == "null-error-model":
                        self.wfile.write(b'data: {"error": null}\n\n')
                    chunk = {"choices": [{"delta": {"content": "OK"}}]}
                    self.wfile.write(
                        ("data: " + json.dumps(chunk) + "\n\n").encode("utf-8")
                    )
                    self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                finally:
                    with state.lock:
                        state.current_in_flight -= 1

        self.server = _HighBacklogHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.hub_url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def __enter__(self) -> "MockBridge":
        self.thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5.0)


def test_all_orchestration_models_parallel_execution_and_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models_md = _write_models_fixture(tmp_path / "models.md")
    entries = _load_entries(models_md)
    monkeypatch.setattr(
        smoke_models_module,
        "_load_fleet_config",
        lambda: (
            frozenset(
                {
                    "claude-sonnet-5-5",
                    "gpt-6.1-sol",
                    "gemini-4-argon",
                    "muse-wonder-full-1.0",
                    "gemini-3.8-flash",
                    "claude-haiku-5-5",
                    "deepseek-v4.1-flash-free",
                }
            ),
            {},
        ),
    )

    with MockBridge() as bridge:
        results = run_parallel_smoke(
            entries, bridge.hub_url, timeout_s=10.0, max_workers=32
        )

    assert len(results) == len(entries)
    assert all(result["ok"] is True for result in results), results
    assert all(result["status"] == "STREAM_OK" for result in results)
    assert bridge.state.max_in_flight >= min(6, len(entries))

    subagent_ids = [record["subagent_id"] for record in bridge.state.records]
    assert all(subagent_ids)
    assert len(subagent_ids) == len(set(subagent_ids))
    assert all(
        record["authorization"] and record["authorization"].startswith("Bearer ")
        for record in bridge.state.records
    )

    deepseek_records = [
        record
        for record in bridge.state.records
        if "deepseek-v4.1-flash" in record["subagent_id"]
    ]
    assert deepseek_records
    deepseek_body = deepseek_records[0]["body"]
    assert deepseek_body["model"] == "deepseek-v4.1-flash-free"
    assert deepseek_body["reasoning_effort"] == "off"
    assert deepseek_body["thinking"] == {"type": "disabled"}


def test_parallel_subprocesses_spawn_independent_pgids_via_bridge(
    tmp_path: Path,
) -> None:
    models_md = _write_models_fixture(tmp_path / "models.md")
    entries = _load_entries(models_md)
    batch = entries[:6]
    assert len(batch) == 6

    with MockBridge() as bridge:
        results = run_parallel_smoke(
            batch,
            bridge.hub_url,
            timeout_s=15.0,
            max_workers=6,
            use_subprocesses=True,
        )

    assert len(results) == 6
    assert all(result["ok"] is True for result in results), results
    assert all(result["status"] == "STREAM_OK" for result in results)
    worker_pids = [result["worker_pid"] for result in results]
    assert all(isinstance(pid, int) and pid > 0 for pid in worker_pids)
    assert len(worker_pids) == len(set(worker_pids))
    assert all(result["worker_pgid"] == result["worker_pid"] for result in results)
    assert all(result["worker_pgid"] != os.getpgrp() for result in results)
    assert bridge.state.max_in_flight >= min(6, len(batch))

    subagent_ids = [record["subagent_id"] for record in bridge.state.records]
    assert len(subagent_ids) == 6
    assert all(subagent_ids)
    assert len(subagent_ids) == len(set(subagent_ids))


def test_parse_models_effort_annotations_and_gemini_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models_md = tmp_path / "models.md"
    models_md.write_text(
        """# Models

### Ревью ответа — лёгкий луп

| Модель | Effort | Family |
| --- | --- | --- |
| `gemini-3.8-flash` + `deepseek-v4.1-flash` + `gpt-6.1-terra` | `off` (DeepSeek); `medium` (Google, OpenAI) | Google + DeepSeek + OpenAI |
""",
        encoding="utf-8",
    )

    entries = parse_models_md(models_md)
    by_model = {entry.model_id: entry for entry in entries}
    assert by_model["gemini-3.8-flash"].effort == "medium"
    assert by_model["deepseek-v4.1-flash"].effort == "off"
    assert by_model["gpt-6.1-terra"].effort == "medium"

    monkeypatch.setattr(
        smoke_models_module,
        "_load_fleet_config",
        lambda: (
            frozenset({"gemini-3.8-flash", "deepseek-v4.1-flash-free"}),
            {"canonical-alias": "wire-target"},
        ),
    )
    payload = build_bridge_payload("gemini-3.8-flash", effort="off")
    assert payload["model"] == "gemini-3.8-flash"
    assert payload["reasoning_effort"] == "off"
    assert payload["thinking"] == {"type": "disabled"}

    alias_payload = build_bridge_payload("canonical-alias", effort="high")
    assert alias_payload["model"] == "wire-target"
    free_payload = build_bridge_payload("deepseek-v4.1-flash", effort="off")
    assert free_payload["model"] == "deepseek-v4.1-flash-free"


def test_temp_off_empty_marker_and_same_line_extraction(tmp_path: Path) -> None:
    empty_notes = tmp_path / "empty-notes.md"
    empty_notes.write_text(
        """# Model notes

## TEMP OFF

Список `TEMP OFF` пуст — все канонические модели активны.

- `muse-wonder-full-1.0`
""",
        encoding="utf-8",
    )
    assert parse_temp_off_models(empty_notes) == set()

    notes = tmp_path / "marked-notes.md"
    notes.write_text(
        """# Model notes

## TEMP OFF

- `limited-model` — TEMP OFF
- `not-limited-model` — active
| `another-limited-model` | TEMP OFF |

## Other section

- `outside-model` — TEMP OFF
""",
        encoding="utf-8",
    )
    assert parse_temp_off_models(notes) == {
        "limited-model",
        "another-limited-model",
    }


def test_model_limit_exception_handling_and_strict_mode(
    tmp_path: Path,
) -> None:
    notes = tmp_path / "model-notes.md"
    notes.write_text(
        """# Model notes

## TEMP OFF

- `limited-model` — TEMP OFF
- `another-limited-model` — TEMP OFF

## Other section

- `outside-model` — TEMP OFF
""",
        encoding="utf-8",
    )
    assert parse_temp_off_models(notes) == {
        "limited-model",
        "another-limited-model",
    }

    limited_entry = ModelEntry("Coder", "limited-model", "high", "Test")
    quota_entry = ModelEntry("Coder", "quota-model", "high", "Test")
    failure_entry = ModelEntry("Coder", "failure-model", "high", "Test")

    assert is_model_limit_error(500, "connection pool exhausted") is False
    assert is_model_limit_error(502, "upstream quota service down") is False
    assert is_model_limit_error(
        400, '{"error":{"type":"quota_exceeded"}}'
    ) is True

    with MockBridge() as bridge:
        skipped = run_parallel_smoke(
            [limited_entry],
            bridge.hub_url,
            temp_off_models=parse_temp_off_models(notes),
        )
        assert skipped[0]["status"] == "SKIPPED_LIMIT"
        assert skipped[0]["ok"] is True
        assert skipped[0]["detail"]
        assert bridge.state.records == []

        bridge.state.behaviors["quota-model"] = 429
        bridge.state.behaviors["failure-model"] = 500
        bridge.state.behaviors["pool-failure-model"] = 500
        results = run_parallel_smoke(
            [quota_entry, failure_entry],
            bridge.hub_url,
            timeout_s=5.0,
            max_workers=2,
        )
        strict_result = run_parallel_smoke(
            [quota_entry],
            bridge.hub_url,
            timeout_s=5.0,
            max_workers=1,
            strict_limits=True,
        )
        with pytest.raises(ModelLimitException):
            smoke_test_model(
                bridge.hub_url,
                "quota-model",
                timeout_s=5.0,
                raise_on_limit=True,
            )
        ok, status, elapsed = smoke_test_model(
            bridge.hub_url, "pool-failure-model", timeout_s=5.0
        )
        assert ok is False
        assert status.startswith("HTTP 500")
        assert isinstance(elapsed, float)

        null_ok, null_status, null_elapsed = smoke_test_model(
            bridge.hub_url, "null-error-model", timeout_s=5.0
        )
        assert null_ok is True
        assert null_status == "STREAM_OK"
        assert isinstance(null_elapsed, float)

    by_model = {result["model_id"]: result for result in results}
    assert by_model["quota-model"]["status"] == "SKIPPED_LIMIT"
    assert by_model["quota-model"]["ok"] is True
    assert by_model["quota-model"]["detail"]
    assert by_model["failure-model"]["ok"] is False
    assert by_model["failure-model"]["status"].startswith("HTTP 500")
    assert strict_result[0]["status"] == "SKIPPED_LIMIT"
    assert strict_result[0]["ok"] is False


@pytest.mark.skipif(
    os.environ.get("BRIDGE_LIVE_SMOKE") != "1",
    reason="set BRIDGE_LIVE_SMOKE=1 to test the real bridge on port 9882",
)
def test_live_bridge_9882_parallel_models_and_subprocesses() -> None:
    if not DEFAULT_MODELS_MD.is_file():
        pytest.skip(f"canonical models file is absent: {DEFAULT_MODELS_MD}")

    entries = deduplicate_models_for_parallel(parse_models_md(DEFAULT_MODELS_MD))
    assert entries
    temp_off = parse_temp_off_models(DEFAULT_MODEL_NOTES_MD)
    hub_url = "http://127.0.0.1:9882/v1"

    parallel_results = run_parallel_smoke(
        entries,
        hub_url,
        timeout_s=45.0,
        max_workers=min(128, max(16, len(entries))),
        temp_off_models=temp_off,
    )
    subprocess_results = run_parallel_smoke(
        entries[:3],
        hub_url,
        timeout_s=45.0,
        max_workers=3,
        use_subprocesses=True,
        temp_off_models=temp_off,
    )

    results = parallel_results + subprocess_results
    allowed_statuses = {"STREAM_OK", "DONE_OK", "SKIPPED_LIMIT"}
    for result in results:
        assert result["ok"] is True, result
        assert result["status"] in allowed_statuses, result
    assert sum(
        1
        for result in results
        if str(result["status"]).startswith(("STREAM_OK", "DONE_OK"))
    ) >= 1


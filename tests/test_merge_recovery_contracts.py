"""Регрессии стыка PR #27 с извлечёнными в main валидатором и SSE runner."""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.fleet_model_validation import normalize_model
from core.routing_contract import FleetViolation


@pytest.mark.parametrize("status", ["unsupported", "unverified"])
def test_tools_capability_is_independent_of_image_verification(status: str) -> None:
    model = {
        "backend": "test",
        "efforts": ["high"],
        "default_effort": "high",
        "input": ["text", "tools"],
        "images": {"status": status, "method": None},
    }
    result = normalize_model(model, "m", 3, {"test": {"enabled": True}}, False)
    assert result is not None and result["input"] == ["text", "tools"]
    assert result["images"]["status"] == status
    model["input"] = ["text", "tools", "image"]
    with pytest.raises(FleetViolation, match="status_inconsistent"):
        normalize_model(model, "m", 3, {"test": {"enabled": True}}, False)


def _runner(monkeypatch: pytest.MonkeyPatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "bridges/agy-bridge"))
    for flag in ("MIDSTREAM_RETRY", "TOOL_ROLLBACK", "PRECOMMIT_FLUSH"):
        monkeypatch.setenv(f"BRIDGE_STREAM_{flag}_ENABLED", "false")
    return importlib.import_module("agy_runtime.sse_body_runner")


def _handler(wire: list[str], result: dict, *, content: bool):
    def once(_ctx, text, *_callbacks):
        if content:
            assert text("partial")
        return result

    return SimpleNamespace(
        wfile=io.BytesIO(),
        send_response=Mock(),
        send_header=Mock(),
        end_headers=Mock(),
        _arm_flush_window=Mock(),
        _graceful_notice=Mock(),
        _usage_payload=lambda usage, _resolved: usage,
        _send=Mock(),
        close_connection=False,
        _emit=lambda value: wire.append(value) or True,
        _error_body=lambda out, _enabled: out.get("error"),
        _run_once=once,
    )


def _hooks():
    return (lambda _key, default=False: default, Mock(), lambda: "stop", Mock())


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": 17, "completion_tokens": 9, "total_tokens": 26},
        {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    ],
)
def test_extracted_agy_runner_retains_only_positive_error_usage(monkeypatch, usage):
    runner, wire = _runner(monkeypatch), []
    result = {
        "state": "agy_error",
        "rc": 1,
        "err": "MALFORMED_FUNCTION_CALL",
        "error": {"type": "server_error", "code": 502, "message": "parse failed"},
        "usage": usage,
    }
    handler = _handler(wire, result, content=True)
    runner.serve_sse_body(handler, {"model": "m"}, _hooks())
    frames = [json.loads(part[6:]) for part in wire if part.startswith("data: {")]
    errors = [frame for frame in frames if "error" in frame]
    assert len(errors) == 1
    if usage["total_tokens"]:
        assert errors[0]["usage"] == usage
    else:
        assert "usage" not in errors[0]
    assert wire[-1] == "data: [DONE]\n\n"


def test_extracted_agy_runner_keeps_capacity_503_before_commit(monkeypatch):
    runner, wire = _runner(monkeypatch), []
    error = {"type": "model_capacity_exhausted", "code": 503, "message": "capacity"}
    result = {"state": "capacity_exhausted", "rc": 1, "error": error}
    handler = _handler(wire, result, content=False)
    ctx = {"model": "m"}
    runner.serve_sse_body(handler, ctx, _hooks())
    handler._send.assert_called_once_with(503, {"error": error})
    assert not wire and not ctx["stream_committed"]


def test_pool_retains_dynamic_hooks_at_legacy_import_path(monkeypatch):
    from adapters import passthrough_adapter as adapter

    connection = object()
    monkeypatch.setattr(adapter, "time", SimpleNamespace(monotonic=lambda: 123.0))
    monkeypatch.setattr(
        adapter,
        "http",
        SimpleNamespace(
            client=SimpleNamespace(HTTPConnection=lambda *args, **kwargs: connection)
        ),
    )
    pool = adapter.PassthroughConnectionPool()
    try:
        assert pool._monotonic() == 123.0
        assert pool._connection_fn("fixture", 1, 1) is connection
    finally:
        pool.close_all()


@pytest.mark.parametrize("field", ["api_key_env", "api_key_ref"])
def test_hot_reload_reaches_route_owned_wire_and_revokes(monkeypatch, tmp_path, field):
    from tests.transport_test_support import RecordingUpstream, make_adapter

    env_file = tmp_path / ".env"
    monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("BRIDGE_ENV_CACHE_TTL_S", "0")
    monkeypatch.setenv("MERGE_WIRE_KEY", "stale-process-key")
    config = {
        field: "env:MERGE_WIRE_KEY" if field == "api_key_ref" else "MERGE_WIRE_KEY"
    }
    upstream = RecordingUpstream()
    with upstream:
        adapter = make_adapter(upstream, config)
        try:
            for key in ("first-route-key", "rotated-route-key"):
                env_file.write_text(f"MERGE_WIRE_KEY={key}\n", encoding="utf-8")
                connection = adapter._open(
                    "/v1/chat/completions",
                    b"{}",
                    {"Authorization": "Bearer client-key"},
                )
                try:
                    connection.getresponse().read()
                finally:
                    connection.close()
                assert (
                    dict(upstream.requests[-1].headers)["Authorization"]
                    == f"Bearer {key}"
                )
            env_file.write_text('MERGE_WIRE_KEY=""\n', encoding="utf-8")
            with pytest.raises(ValueError, match="outbound_credential_unavailable"):
                adapter._open(
                    "/v1/chat/completions", b"{}", {"X-Api-Key": "client-key"}
                )
            assert upstream.post_count == 2
        finally:
            adapter.shutdown()

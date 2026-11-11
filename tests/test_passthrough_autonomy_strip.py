"""Default-off rollout удаления CAB-only ``autonomy`` на passthrough-маршрутах."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.catalog_flags import (  # noqa: E402
    FLAG_STRIP_PASSTHROUGH_AUTONOMY,
    strip_passthrough_autonomy_enabled,
)
from core import passthrough_autonomy as policy  # noqa: E402

route = importlib.import_module("test_passthrough_routing").route


def _set_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, enabled: bool) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv(
        FLAG_STRIP_PASSTHROUGH_AUTONOMY, "true" if enabled else "false"
    )


def test_flag_false_preserves_legacy_passthrough_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.delenv(FLAG_STRIP_PASSTHROUGH_AUTONOMY, raising=False)
    req = {
        "model": "gpt-6.1-terra",
        "autonomy": "off",
        "extra_body": {"autonomy": "medium", "cwd": "/tmp"},
    }
    raw = json.dumps(req).encode()

    clean_raw, clean_req = server._strip_passthrough_env(raw, req)

    assert strip_passthrough_autonomy_enabled() is False
    assert clean_raw is raw
    assert clean_req is req


def test_flag_true_validates_and_strips_autonomy_before_upstream(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    body = {
        "model": "gpt-6.1-terra",
        "autonomy": "off",
        "extra_body": {"autonomy": "medium", "cwd": "/tmp"},
    }
    handler, _ = route(body)
    handler._send.assert_not_called()
    handler._serve_passthrough.assert_called_once()

    adapter = Mock(id="capture", limits=Mock())
    lease = SimpleNamespace(
        record_success=Mock(), record_failure=Mock(), record_discard=Mock()
    )
    passthrough_handler = Mock(
        path="/v1/chat/completions",
        headers={},
        _trace=None,
        _current_lease=Mock(return_value=lease),
        _trace_log_fields=Mock(return_value=""),
    )
    sink = SimpleNamespace(status=200, _client_gone_flag=False)
    monkeypatch.setattr(server, "_HandlerSink", Mock(return_value=sink))
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)
    monkeypatch.setattr(server, "_PENALTY_TRACKER", Mock())

    raw = json.dumps(body).encode()
    server.Handler._serve_passthrough(
        passthrough_handler, adapter, raw, body, "gpt-6.1-terra"
    )

    sent = adapter.handle.call_args.kwargs
    assert json.loads(sent["raw_body"]) == sent["request"]
    assert "autonomy" not in sent["request"]
    assert sent["request"]["extra_body"] == {"cwd": "/tmp"}
    assert body["autonomy"] == "off"
    assert body["extra_body"]["autonomy"] == "medium"


def test_flag_true_rejects_invalid_autonomy_before_passthrough(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_flag(monkeypatch, tmp_path, True)

    handler, _ = route({"model": "gpt-6.1-terra", "autonomy": "bogus"})

    assert handler._send.call_args.args[0] == 400
    assert handler._send.call_args.args[1]["error"]["type"] == "unsupported_autonomy"
    handler._serve_passthrough.assert_not_called()


def test_target_model_and_validation_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    assert policy.resolve_target_model(None, "requested") == "requested"
    assert policy.passthrough_autonomy_validation_enabled(True) is True
    assert policy.passthrough_autonomy_validation_enabled(False) is False
    assert policy.strip_passthrough_autonomy_enabled(
        lambda _name: (_ for _ in ()).throw(RuntimeError("source"))
    ) is False


def test_prepare_positional_compatibility(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, object]] = []

    def resolve(_requested: object, alias_effort: object, _spec: object, *, enabled: object) -> Any:
        seen.append((alias_effort, enabled))
        return SimpleNamespace(apply=False, value=None)

    monkeypatch.setattr(policy, "resolve_passthrough_effort", resolve)
    single, _ = policy.prepare_passthrough_request(
        {"model": "raw"}, {}, "canonical", object()
    )
    assert single["model"] == "canonical"
    request, _ = policy.prepare_passthrough_request(
        {"model": "raw"}, {}, "canonical", object(), "medium", True
    )
    assert request["model"] == "canonical"
    assert seen == [(None, False), ("medium", True)]
    policy.prepare_passthrough_request({"model": "raw"}, {}, "canonical")
    assert seen[-1] == (None, False)
    with pytest.raises(TypeError):
        policy.prepare_passthrough_request({}, {}, "model", 1, 2, 3, 4)


def test_strip_top_level_only_and_preserve_unicode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_flag(monkeypatch, tmp_path, True)
    request = {"model": "gpt-6.1-terra", "autonomy": "off", "cwd": "/tmp/путь"}
    raw, clean = policy.strip_passthrough_request(json.dumps(request).encode(), request)
    assert "autonomy" not in clean
    assert "путь".encode() in raw

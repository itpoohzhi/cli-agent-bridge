"""AD-007/008: настоящий do_POST без сети, с наблюдаемой границей raw-шва."""

import json
import sys
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from core.backend_adapter import AdapterRegistry  # noqa: E402


@pytest.fixture
def route(monkeypatch, tmp_path):
    data = json.loads((server.ROOT / "fleet.json").read_text())
    data["backends"]["codex"]["enabled"] = True
    catalog = server._build_catalog(data)
    monkeypatch.setattr(server, "FLEET", catalog)
    monkeypatch.setattr(
        server,
        "BACKENDS",
        AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, server),
    )
    monkeypatch.setattr(server, "AUTH_KEY", "hub-test-key")
    monkeypatch.setattr(
        server,
        "TOKEN_CACHE",
        server.TokenCache(
            path=tmp_path / ".env", environ={"BRIDGE_KEY": "hub-test-key"}
        ),
    )
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    budget = server._ByteBudget(1_000_000)
    monkeypatch.setattr(server, "_budget", budget)

    def post(body, auth="Bearer hub-test-key", error=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        initial = budget._used
        handler = object.__new__(server.Handler)
        handler.path = "/v1/chat/completions"
        handler.client_address = ("127.0.0.1", 12345)
        handler.headers = Message()
        handler.headers["Content-Length"] = str(len(raw))
        if auth is not None:
            handler.headers["Authorization"] = auth
        def read(length):
            assert budget._used == initial + length
            return raw[:length]
        handler.rfile = Mock(read=Mock(side_effect=read))
        handler._send = Mock()
        handler._log_reject = Mock()
        handler._serve_passthrough = Mock(side_effect=error)
        with patch.object(budget, "reserve", wraps=budget.reserve) as reserve, patch.object(budget, "release", wraps=budget.release) as release:
            try:
                handler.do_POST()
            finally:
                assert budget._used == initial
                if handler.rfile.read.called:
                    release.assert_called_once_with(len(raw))
                else:
                    release.assert_not_called()
        return handler, reserve

    return post


# gpt-6.1-sol первичен на droid (priority 10), поэтому passthrough-маршрут проверяется на моделях codex/agy.
BACKEND_OF = {"gpt-6.1-terra": "codex", "gemini-4-argon": "agy"}


@pytest.mark.parametrize("model", list(BACKEND_OF))
@pytest.mark.parametrize("effort", ["low", "medium", "high"])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("auth", ["hub-test-key", "Bearer hub-test-key"])
def test_exact_route_preserves_body_and_reserves_budget(
    route, model, effort, stream, auth
):
    body = {"model": model, "reasoning_effort": effort, "stream": stream}
    handler, reserve = route(body, auth)
    handler._send.assert_not_called()
    handler._serve_passthrough.assert_called_once()
    adapter, raw, request, resolved = handler._serve_passthrough.call_args.args
    assert adapter.id == BACKEND_OF[model]
    assert resolved == model
    assert request == json.loads(raw) == body
    reserve.assert_called_once_with(len(raw))


@pytest.mark.parametrize("model", [None, "", " ", " gpt-6.1-terra "])
def test_default_cannot_open_passthrough_without_exact_id(route, monkeypatch, model):
    monkeypatch.setattr(server, "MODEL_ID", "gpt-6.1-terra")
    handler, reserve = route({"model": model})
    assert handler._send.call_args.args[0] == 400
    handler._serve_passthrough.assert_not_called()
    reserve.assert_called_once()


@pytest.mark.parametrize(
    "model,status", [("unknown-model", 404), (123, 400), ([], 400)]
)
def test_unknown_and_invalid_models_fail_before_backend(route, model, status):
    handler, _ = route({"model": model})
    assert handler._send.call_args.args[0] == status
    if status == 404:
        assert handler._send.call_args.args[1]["error"]["code"] == "model_not_found"
    handler._serve_passthrough.assert_not_called()


def test_invalid_auth_cannot_execute_cli_backend(route):
    handler, reserve = route({"model": "muse-wonder-full-1.0"}, auth="Bearer upstream-test-key")
    assert handler._send.call_args.args[0] == 401
    reserve.assert_not_called()
    handler.rfile.read.assert_not_called()
    handler._serve_passthrough.assert_not_called()


def test_missing_model_cannot_open_default_passthrough(route, monkeypatch):
    monkeypatch.setattr(server, "MODEL_ID", "gpt-6.1-terra")
    handler, reserve = route({})
    assert handler._send.call_args.args[0] == 400
    handler._serve_passthrough.assert_not_called()
    reserve.assert_called_once()


def test_exhausted_body_budget_rejects_before_read(route):
    budget = server._budget
    assert budget.reserve(budget.total - 1)
    handler, reserve = route({"model": "gpt-6.1-sol"})
    assert handler._send.call_args.args[0] == 503
    assert handler._send.call_args.args[1]["error"]["type"] == "overloaded"
    handler.rfile.read.assert_not_called()
    handler._serve_passthrough.assert_not_called()
    reserve.assert_called_once()


@pytest.mark.parametrize("auth", [None, "Bearer hub-test-key"])
def test_invalid_json_releases_body_budget(route, auth):
    handler, reserve = route(b"{", auth)
    assert handler._send.call_args.args[0] == (401 if auth is None else 400)
    if auth is None:
        reserve.assert_not_called()
        handler.rfile.read.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("upstream"), BrokenPipeError("client disconnected")])
def test_upstream_failure_and_disconnect_release_body_budget(route, error):
    with pytest.raises(type(error)):
        route({"model": "gpt-6.1-terra"}, error=error)

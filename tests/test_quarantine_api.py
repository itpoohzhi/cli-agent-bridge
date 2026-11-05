from __future__ import annotations

import ast
import copy
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

import core.model_penalty as penalty_module
from core.model_penalty import ModelPenaltyTracker


@pytest.fixture
def clock(monkeypatch):
    current = [1_700_000_000.0]
    monkeypatch.setattr(penalty_module.time, "time", lambda: current[0])
    return current


@pytest.fixture
def tracker(tmp_path, clock):
    return ModelPenaltyTracker(
        storage_path=tmp_path / "penalties.json",
        max_start_fails=3,
        cooldown_seconds=10.0,
    )


def test_initial_payload(tracker):
    assert tracker.configured_max_start_fails == 3
    assert tracker.max_start_fails == 3
    assert tracker.enabled is True
    assert tracker.get_quarantine_payload(["a", "b"]) == {
        "enabled": True,
        "max_start_fails": 3,
        "cooldown_seconds": 10.0,
        "penalized_count": 0,
        "penalized_models": [],
        "available_models": ["a", "b"],
    }


def test_toggle_persists_and_reloads_across_instances(tracker):
    assert tracker.set_enabled(False) is False
    assert tracker.max_start_fails == 999999999

    raw = json.loads(tracker.storage_path.read_text())
    assert raw["_meta"] == {"quarantine_enabled": False, "configured_max_start_fails": 3}

    other = ModelPenaltyTracker(tracker.storage_path, max_start_fails=7, cooldown_seconds=10)
    assert other.enabled is False
    assert other.configured_max_start_fails == 3
    assert other.max_start_fails == 999999999
    assert other.get_all_penalties() == {}

    assert other.set_enabled(True) is True
    assert other.max_start_fails == 3

    assert tracker.get_quarantine_payload()["enabled"] is True
    assert tracker.max_start_fails == 3


def test_manual_penalty_normalization_and_expiration(tracker, clock):
    status = tracker.manually_penalize("  MODEL-A  ", 30)
    assert status == {
        "model": "model-a",
        "fails": 1,
        "is_penalized": True,
        "remaining_cooldown": 30,
        "penalized_until": clock[0] + 30,
        "last_fail_at": clock[0],
        "last_error": "manually penalized by user",
    }
    assert tracker.is_penalized("MODEL-A") == (True, 30)

    payload = tracker.get_quarantine_payload()
    assert payload["penalized_count"] == 1
    assert payload["penalized_models"] == [status]

    clock[0] += 30
    assert tracker.get_quarantine_payload()["penalized_count"] == 0
    assert tracker.is_penalized("model-a") == (False, 0)
    persisted = json.loads(tracker.storage_path.read_text())
    assert persisted["model-a"]["fails"] == 0
    assert persisted["model-a"]["penalized_until"] == 0


def test_disabled_quarantine_preserves_existing_penalties(tracker):
    tracker.manually_penalize("a", 60)
    tracker.set_enabled(False)

    assert tracker.is_penalized("a") == (False, 0)
    payload = tracker.get_quarantine_payload()
    assert payload["enabled"] is False
    assert payload["penalized_count"] == 1

    tracker.set_enabled(True)
    assert tracker.is_penalized("a") == (True, 60)


def test_disabled_threshold_does_not_trigger_normal_failures(tracker):
    tracker.set_enabled(False)
    for _ in range(4):
        penalized, _, until = tracker.record_start_failure("a", "startup error")
        assert penalized is False
        assert until == 0


def test_unban_resets_failure_and_escalation(tracker):
    for _ in range(3):
        tracker.record_start_failure("a", "startup error")
    tracker.unpenalize_model("A")

    status = tracker.get_model_status("a")
    assert status["fails"] == 0
    assert status["penalized_until"] == 0
    assert status["last_error"] is None
    raw = json.loads(tracker.storage_path.read_text())
    assert raw["a"]["penalty_trips"] == 0

    tracker.unpenalize_model("missing")
    assert "missing" not in tracker.get_all_penalties()


def test_clear_all_preserves_configuration_and_hides_meta(tracker):
    tracker.manually_penalize("a")
    tracker.set_enabled(False)
    tracker.reset_all()

    assert tracker.get_all_penalties() == {}
    payload = tracker.get_quarantine_payload()
    assert payload["enabled"] is False
    assert payload["penalized_models"] == []

    assert json.loads(tracker.storage_path.read_text()) == {
        "_meta": {
            "quarantine_enabled": False,
            "configured_max_start_fails": 3,
        }
    }


def test_legacy_document_without_metadata(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "MODEL-A": {
                    "fails": 1,
                    "penalized_until": 0,
                    "last_fail_at": 123,
                    "last_error": "startup failed",
                }
            }
        )
    )
    tracker = ModelPenaltyTracker(path, max_start_fails=4)
    assert tracker.enabled is True
    assert tracker.max_start_fails == 4
    assert tracker.get_all_penalties()["model-a"]["fails"] == 1


@pytest.mark.parametrize(
    "meta",
    [
        {},
        {"quarantine_enabled": "false", "configured_max_start_fails": True},
        {"quarantine_enabled": None, "configured_max_start_fails": 0},
        {"configured_max_start_fails": "8"},
    ],
)
def test_invalid_metadata_uses_defaults(tmp_path, meta):
    path = tmp_path / "penalties.json"
    path.write_text(json.dumps({"_meta": meta}))
    tracker = ModelPenaltyTracker(path, max_start_fails=4)
    assert tracker.enabled is True
    assert tracker.configured_max_start_fails == 4
    assert tracker.max_start_fails == 4
    assert tracker.get_all_penalties() == {}


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan"), True])
def test_invalid_manual_duration_does_not_mutate(tracker, duration):
    with pytest.raises(ValueError):
        tracker.manually_penalize("a", duration)
    assert tracker.get_all_penalties() == {}


def test_reserved_model_id_cannot_overwrite_metadata(tracker):
    with pytest.raises(ValueError):
        tracker.manually_penalize(" _META ")
    assert tracker.get_all_penalties() == {}


def test_infrastructure_errors_are_not_counted(tracker):
    assert tracker.record_start_failure("a", "http_502 bad gateway") == (False, 0, 0)


def test_active_cooldown_is_not_extended(tracker, clock):
    tracker.manually_penalize("a", 30)
    before = tracker.storage_path.read_bytes()
    clock[0] += 5
    assert tracker.record_start_failure("a", "startup error") == (True, 1, clock[0] + 25)
    assert tracker.storage_path.read_bytes() == before


def _load_quarantine_methods(namespace):
    """Compile the actual quarantine branches without importing server.py."""
    server_path = Path(__file__).resolve().parents[1] / "server.py"
    tree = ast.parse(server_path.read_text(encoding="utf-8"))

    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(child, ast.FunctionDef)
            and child.name == "_handle_quarantine_post"
            for child in node.body
        )
    ]
    assert len(candidates) == 1, (
        "Expected one HTTP handler class with _handle_quarantine_post"
    )
    methods = {
        node.name: node
        for node in candidates[0].body
        if isinstance(node, ast.FunctionDef)
    }

    selected = []
    for method_name in ("do_GET", "do_POST"):
        original = methods[method_name]
        branches = [
            node
            for node in ast.walk(original)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "path"
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Eq)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "/v1/quarantine"
        ]
        assert len(branches) == 1, (
            f"Expected one quarantine route in {method_name}"
        )
        method = copy.deepcopy(original)
        method.decorator_list = []
        method.body = [
            ast.parse(
                'path = self.path.split("?", 1)[0]'
            ).body[0],
            copy.deepcopy(branches[0]),
            ast.parse(
                'self._send(404, {"error": {"message": "not found"}})'
            ).body[0],
        ]
        selected.append(method)

    post_handler = copy.deepcopy(methods["_handle_quarantine_post"])
    post_handler.decorator_list = []
    selected.append(post_handler)

    module = ast.fix_missing_locations(
        ast.Module(body=selected, type_ignores=[])
    )
    exec(compile(module, str(server_path), "exec"), namespace)

    return {
        name: namespace[name]
        for name in ("do_GET", "do_POST", "_handle_quarantine_post")
    }


@pytest.fixture
def api(tracker):
    namespace = {
        "json": json,
        "_PENALTY_TRACKER": tracker,
        "_auth_ok": lambda handler: handler.headers.get("Authorization") == "Bearer test-secret",
        "BACKENDS": SimpleNamespace(models=lambda: [SimpleNamespace(id="model-a"), SimpleNamespace(id="model-b")]),
    }
    methods = _load_quarantine_methods(namespace)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status_code, dict_payload):
            raw = json.dumps(dict_payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _reject(self, status_code, err_type, err_msg):
            self._send(
                status_code,
                {"error": {"message": err_msg, "type": err_type}},
            )

        def log_message(self, format, *args):
            pass

    for name, method in methods.items():
        setattr(Handler, name, method)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method="GET", body=None, *, authorized=True, raw=None):
        headers = {}
        if authorized:
            headers["Authorization"] = "Bearer test-secret"
        if raw is None and body is not None:
            raw = json.dumps(body).encode("utf-8")
        if raw is not None:
            headers["Content-Type"] = "application/json"

        connection = HTTPConnection(*server.server_address, timeout=5)
        try:
            connection.request(
                method, "/v1/quarantine", body=raw, headers=headers
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_http_requires_authorization(api, tracker, method):
    status, body = api(method, {"action": "ban", "model": "a"}, authorized=False)
    assert status == 401
    assert body == {
        "error": {
            "message": "unauthorized",
            "type": "auth_error",
            "code": 401,
        }
    }
    assert tracker.get_all_penalties() == {}


def test_http_get_catalog(api):
    status, body = api()
    assert status == 200
    assert body["enabled"] is True
    assert body["max_start_fails"] == 3
    assert body["available_models"] == ["model-a", "model-b"]
    assert body["penalized_count"] == 0


def test_http_toggle(api):
    status, body = api("POST", {"action": "set_enabled", "enabled": False})
    assert status == 200
    assert body == {
        "ok": True,
        "action": "set_enabled",
        "enabled": False,
        "max_start_fails": 999999999,
    }
    assert api()[1]["enabled"] is False

    status, body = api("POST", {"action": "set_enabled"})
    assert status == 200
    assert body["enabled"] is True
    assert body["max_start_fails"] == 3


def test_http_ban_and_unban(api):
    status, body = api("POST", {"action": "ban", "model": "MODEL-A", "duration_s": 45})
    assert status == 200
    assert body["action"] == "ban"
    assert body["model"] == "MODEL-A"
    assert body["status"]["model"] == "model-a"
    assert body["status"]["remaining_cooldown"] == 45
    assert api()[1]["penalized_count"] == 1

    status, body = api("POST", {"action": "unban", "model": "model-a"})
    assert status == 200
    assert body == {"ok": True, "action": "unban", "model": "model-a"}
    assert api()[1]["penalized_count"] == 0


def test_http_default_duration(api):
    status, body = api("POST", {"action": "ban", "model": "a"})
    assert status == 200
    assert body["status"]["remaining_cooldown"] == 300


def test_http_clear_all_preserves_disabled_setting(api):
    api("POST", {"action": "ban", "model": "a"})
    api("POST", {"action": "set_enabled", "enabled": False})
    status, body = api("POST", {"action": "clear_all"})
    assert status == 200
    assert body == {"ok": True, "action": "clear_all"}

    payload = api()[1]
    assert payload["enabled"] is False
    assert payload["penalized_count"] == 0


@pytest.mark.parametrize(
    "body",
    [
        [],
        None,
        {"action": "set_enabled", "enabled": "false"},
        {"action": "set_enabled", "enabled": 0},
        {"action": "ban"},
        {"action": "ban", "model": " "},
        {"action": "ban", "model": 123},
        {"action": "ban", "model": "_meta"},
        {"action": "unban", "model": ""},
        {"action": "ban", "model": "a", "duration_s": -1},
        {"action": "ban", "model": "a", "duration_s": "NaN"},
        {"action": "ban", "model": "a", "duration_s": "Infinity"},
        {"action": "ban", "model": "a", "duration_s": None},
        {"action": "ban", "model": "a", "duration_s": True},
    ],
)
def test_http_invalid_requests(api, body):
    status, response = api("POST", raw=json.dumps(body).encode("utf-8"))
    assert status == 400
    assert response["error"]["type"] == "invalid_request"


@pytest.mark.parametrize("raw", [b"", b"{", b"\xff"])
def test_http_invalid_json(api, raw):
    status, body = api("POST", raw=raw)
    assert status == 400
    assert body["error"]["type"] == "invalid_request"


def test_http_unknown_action(api):
    status, body = api("POST", {"action": "unsupported"})
    assert status == 400
    assert body == {
        "error": {
            "message": "unknown action: unsupported",
            "type": "invalid_request",
        }
    }


def test_http_body_size_limit(api):
    status, body = api("POST", raw=b" " * (64 * 1024 + 1))
    assert status == 413
    assert body["error"]["type"] == "invalid_request"


def test_quarantine_accepts_adapter_model_tuples(tracker):
    tuples = [(SimpleNamespace(name="adapter-a"), SimpleNamespace(id="model-a")), (SimpleNamespace(name="adapter-b"), SimpleNamespace(id="model-b"))]
    backends = SimpleNamespace(models=lambda: tuples)
    ns = {"json": json, "_PENALTY_TRACKER": tracker, "_auth_ok": lambda handler: True, "BACKENDS": backends}
    sent = []
    handler = SimpleNamespace(path="/v1/quarantine", _send=lambda status, payload: sent.append((status, payload)))
    _load_quarantine_methods(ns)["do_GET"](handler)
    status, body = sent[0]
    assert status == 200
    assert body["available_models"] == ["model-a", "model-b"]

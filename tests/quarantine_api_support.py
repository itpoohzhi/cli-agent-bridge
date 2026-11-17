"""Карантин через настоящий ingress и HTTP без импорта живого сервера."""

from __future__ import annotations

import ast
import copy
from functools import partial
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from typing import cast

import pytest

from core.http_post_context import PostHandler, PostHost
from core.http_post_ingress import begin_post


def _server_methods():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "server.py").read_text())
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
    assert len(candidates) == 1
    return {
        node.name: node
        for node in candidates[0].body
        if isinstance(node, ast.FunctionDef)
    }


def _get_method(original):
    target = ast.dump(ast.parse("path == '/v1/quarantine'", mode="eval").body)
    branches = [
        node
        for node in ast.walk(original)
        if isinstance(node, ast.If) and ast.dump(node.test) == target
    ]
    assert len(branches) == 1
    method = copy.deepcopy(original)
    method.decorator_list = []
    method.body = [
        ast.parse('path = self.path.split("?", 1)[0]').body[0],
        copy.deepcopy(branches[0]),
        ast.parse('self._send(404, {"error": {"message": "not found"}})').body[0],
    ]
    return method


def _post(handler):
    return begin_post(cast(PostHandler, handler), cast(PostHost, object()))


def load_quarantine_methods(namespace):
    """GET извлекается из сервера, POST проходит общий пролог ingress."""
    methods = _server_methods()
    post_handler = copy.deepcopy(methods["_handle_quarantine_post"])
    post_handler.decorator_list = []
    helpers = [copy.deepcopy(methods[name]) for name in ("_send_error_envelope", "_serve_quarantine_get")]
    for helper in helpers:
        helper.decorator_list = []
    module = ast.fix_missing_locations(
        ast.Module(body=[_get_method(methods["do_GET"]), post_handler, *helpers], type_ignores=[])
    )
    exec(compile(module, "server.py", "exec"), namespace)

    def do_get(handler):
        for name in ("_send_error_envelope", "_serve_quarantine_get"):
            if not hasattr(handler, name):
                setattr(handler, name, partial(namespace[name], handler))
        return namespace["do_GET"](handler)

    return {
        "do_GET": do_get,
        "do_POST": _post,
        "_handle_quarantine_post": namespace["_handle_quarantine_post"],
        "_serve_quarantine_get": namespace["_serve_quarantine_get"],
        "_send_error_envelope": namespace["_send_error_envelope"],
    }


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status_code, dict_payload):
        raw = json.dumps(dict_payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _reject(self, status_code, err_type, err_msg):
        self._send(status_code, {"error": {"message": err_msg, "type": err_type}})

    def _telemetry_begin(self):
        pass

    def log_message(self, format, *args):
        pass


def _request(server, method="GET", body=None, *, authorized=True, raw=None):
    headers = {}
    if authorized:
        headers["Authorization"] = "Bearer test-secret"
    if raw is None and body is not None:
        raw = json.dumps(body).encode("utf-8")
    if raw is not None:
        headers["Content-Type"] = "application/json"
    connection = HTTPConnection(*server.server_address, timeout=5)
    try:
        connection.request(method, "/v1/quarantine", body=raw, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


@pytest.fixture
def api(tracker):
    namespace = {
        "json": json,
        "_PENALTY_TRACKER": tracker,
        "_auth_ok": lambda handler: (
            handler.headers.get("Authorization") == "Bearer test-secret"
        ),
        "BACKENDS": SimpleNamespace(
            models=lambda: [
                SimpleNamespace(id="model-a"),
                SimpleNamespace(id="model-b"),
            ]
        ),
    }
    handler = type("Handler", (_Handler,), load_quarantine_methods(namespace))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield partial(_request, server)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

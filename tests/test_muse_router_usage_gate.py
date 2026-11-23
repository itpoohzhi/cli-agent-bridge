"""VER-004: роутер отклоняет exhausted Muse-слоты, Fail-Open при unknown."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.http_post_context import PostRequestContext
from core.http_post_routing import check_muse_usage_gate, resolve_post_route
from core.muse_usage_client import MuseUsageSnapshot

MUSE_MODEL = {"backend": "muse", "default_effort": "high", "efforts": ["high"]}
BARE = "~/" + ".local/" + "bin/" + "mu" + "se"


class FakeClient:
    def __init__(self, snapshot: Any) -> None:
        self.snapshot, self.calls = snapshot, 0

    def get_snapshot(self, **_kw: Any) -> Any:
        self.calls += 1
        if isinstance(self.snapshot, BaseException):
            raise self.snapshot
        return self.snapshot


class FakeHandler:
    def __init__(self) -> None:
        self.path, self.headers, self.sent, self.rejected = "/v1/chat/completions", {}, [], []

    def _reject(self, *a: Any, **_k: Any) -> None:
        self.rejected.append(a)

    def _send(self, status: int, body: Any, **kw: Any) -> None:
        self.sent.append((status, body, kw))

    def _telemetry_meta(self, **_k: Any) -> None:
        pass

    def _reply_error(self, *a: Any, **_k: Any) -> None:
        self.rejected.append(a)


def _resolve(model: dict[str, Any], client: FakeClient, *, usage: bool = True, model_id: str = "muse-wonder-full-1.0") -> Any:
    handler = FakeHandler()
    host = SimpleNamespace(
        MODEL_ID=model_id, FLEET={"models": {model_id: dict(model)}}, INTERNAL_MODEL_IDS=set(),
        _MODEL_NOTES_FILTER=SimpleNamespace(is_blocked=lambda _m: False),
        _PENALTY_TRACKER=SimpleNamespace(get_model_status=lambda _m: {"is_penalized": False}),
        _resolve_model_alias=lambda _m, _models: None, _MUSE_USAGE_CLIENT=client,
        flag_enabled=lambda name: usage if name == "MUSE_USAGE_ROUTER_ENABLED" else False,
    )
    context = PostRequestContext(handler, host)  # type: ignore[arg-type]
    context._request = {"model": model_id}
    return resolve_post_route(context), handler


def _snap(status: str, reset_at: int | None = None) -> MuseUsageSnapshot:
    return MuseUsageSnapshot(status=status, reset_at=reset_at)


def test_exhausted_muse_rejected_503_with_reset_at() -> None:
    client = FakeClient(_snap("exhausted", reset_at=1795446181))
    route, handler = _resolve(dict(MUSE_MODEL), client)
    assert route is None and client.calls == 1
    assert handler.sent[0][0] == 503
    error = handler.sent[0][1]["error"]
    assert error["type"] == "muse_usage_exhausted" and error["reset_at"] == 1795446181


@pytest.mark.parametrize("status", ["unknown", "ok"])
def test_unknown_and_ok_fail_open(status: str) -> None:
    route, handler = _resolve(dict(MUSE_MODEL), FakeClient(_snap(status)))
    assert route is not None and handler.sent == []


def test_client_error_fail_open() -> None:
    route, _handler = _resolve(dict(MUSE_MODEL), FakeClient(RuntimeError("boom")))
    assert route is not None


def test_flag_off_skips_client() -> None:
    client = FakeClient(_snap("exhausted", reset_at=1))
    route, _handler = _resolve(dict(MUSE_MODEL), client, usage=False)
    assert route is not None and client.calls == 0


def test_non_muse_backend_skips_client() -> None:
    client = FakeClient(_snap("exhausted", reset_at=1))
    route, _handler = _resolve({"backend": "codex"}, client, model_id="gpt-x")
    assert route is not None and client.calls == 0


def test_mapping_snapshot_exhausted() -> None:
    route, handler = _resolve(dict(MUSE_MODEL), FakeClient({"status": "exhausted", "reset_at": 42}))
    assert route is None and handler.sent[0][1]["error"]["reset_at"] == 42


def test_direct_gate_non_muse_true() -> None:
    route = SimpleNamespace(model={"backend": "droid"}, model_id="x", host=SimpleNamespace(), handler=FakeHandler())
    assert check_muse_usage_gate(route) is True  # type: ignore[arg-type]


def test_routing_disabled_backend_still_applied() -> None:
    model = {"backend": "muse", "routing": {"disabled_backend": "codex"}}
    client = FakeClient(_snap("exhausted", reset_at=1))
    route, _handler = _resolve(model, client)
    assert route is not None and route.model["backend"] == "codex" and client.calls == 0


def test_hot_path_bounded_wait_does_not_block_on_slow_runner() -> None:
    import time
    from core.muse_usage_client import MuseUsageClient

    def slow_runner(_argv: list[str]) -> tuple[int, str, str]:
        time.sleep(1.5)
        return 0, '{"schemaVersion":1,"allowance":{"tier":"t","window":{"usedPercent":5},"weekly":{"usedPercent":5},"asOfMs":1,"source":"mint"}}', ""

    client = MuseUsageClient(runner=slow_runner, ttl_s=30.0)
    t0 = time.monotonic()
    snap = client.get_snapshot(wait_timeout_s=0.05)
    assert time.monotonic() - t0 < 0.5 and snap.status == "unknown" and snap.error_code == "refresh_pending"


def test_file_limits_and_no_bare_binary() -> None:
    path = Path(__file__).parents[1] / "core" / "http_post_routing.py"
    source = path.read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 300 and BARE not in source
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.end_lineno - node.lineno + 1 <= 50
            assert len(node.args.args) + len(node.args.kwonlyargs) <= 5

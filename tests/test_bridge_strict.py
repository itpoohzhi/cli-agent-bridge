"""Строгие тесты моста: каталог (класс I), effort/model (C-02), журнал, admission.

Уровни каталога берутся из fleet.json; строковый reasoning_effort вне каталога
клампится вниз по шкале EFFORT_ORDER (clamp_effort_downward), нестроковые
значения и reasoning-объект отклоняются до запуска droid.
"""
from __future__ import annotations

import copy
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import (  # noqa: E402
    _DROID_LEGACY_MODELS,
    BridgeCase,
    chat_body,
    droidify_raw_fleet,
    find_model,
    install_droid_stand,
    load_raw_fleet,
    make_proof,
)

REJECT_STRICT = re.compile(
    r"^reject reason=[a-z0-9_]+ model=(claude-sonnet-5-5|gemini-3\.8-flash|grok-4\.7|"
    r"deepseek-v4\.1-flash|gpt-6\.1-sol|glm-5\.3|unknown) model_len=[0-9]+ client=[0-9a-f.:]+$"
)


def test_token_cache_ttl_rotation_and_constant_time(tmp_path, monkeypatch):
    from unittest.mock import patch

    path = tmp_path / ".env"
    path.write_text('BRIDGE_KEY="file-first"\nDROID_DSH_BRIDGE_KEY=legacy\n')
    env = {"BRIDGE_KEY": "env-first"}
    clock = [10.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    cache = server.TokenCache(path=path, environ=env, ttl_s=300)
    assert cache.is_valid("file-first")
    assert cache.is_valid("legacy")
    with patch.object(Path, "read_text", side_effect=AssertionError("cached contents")):
        assert not cache.is_valid("env-first")
        assert not cache.is_valid("")
        assert not cache.is_valid("wrong")
    env["BRIDGE_KEY"] = "env-second"
    assert not cache.is_valid("env-second")
    assert not cache.is_valid("env-first")
    path.write_text("BRIDGE_KEY=file-second-longer\n")
    with patch.object(
        server.hmac, "compare_digest", wraps=server.hmac.compare_digest
    ) as compare:
        assert cache.is_valid("file-second-longer")
        assert compare.called
    assert not cache.is_valid("file-first")
    assert not cache.is_valid("legacy")
    path.unlink()
    assert not cache.is_valid("file-second-longer")
    assert not cache.is_valid("env-second")


def test_token_cache_rejects_stale_global_keys(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=current-file-key\n")
    monkeypatch.setattr(server, "AUTH_KEY", "revoked-global-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "revoked-global-key")
    monkeypatch.setattr(server.TOKEN_CACHE, "_path", path)
    monkeypatch.setattr(server.TOKEN_CACHE, "_env", {})
    monkeypatch.setattr(server.TOKEN_CACHE, "_next_check", 0)
    monkeypatch.setattr(server.TOKEN_CACHE, "_signature", None)
    monkeypatch.setattr(server.TOKEN_CACHE, "_file_keys", ())
    assert server.TOKEN_CACHE.is_valid("current-file-key")
    assert not server.TOKEN_CACHE.is_valid("revoked-global-key")


def test_token_cache_rejects_module_keys_without_file_keys(tmp_path, monkeypatch):
    """Без файловых ключей TokenCache не принимает модульные ключи monkeypatch."""
    monkeypatch.setattr(server, "AUTH_KEY", "module-auth-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "module-bridge-key")
    cache = server.TokenCache(path=tmp_path / "missing", environ={})
    assert not cache.is_valid("module-auth-key")
    assert not cache.is_valid("module-bridge-key")
    assert not cache.is_valid("wrong-key")


def test_external_peer_upstream_token_rejected_before_body(monkeypatch):
    """Внешний IP с upstream-токеном без мастер-ключа получает 401 до чтения тела."""
    from email.message import Message
    from unittest.mock import Mock

    from adapters.passthrough_adapter import PassthroughAdapter
    from core.backend_adapter import AdapterRegistry

    registry = AdapterRegistry()
    registry.register(
        PassthroughAdapter(
            "test",
            {"base_url": "http://127.0.0.1:2455/v1", "api_key": "known-upstream-key"},
            dict,
        )
    )
    monkeypatch.setattr(server, "BACKENDS", registry)
    monkeypatch.setattr(server, "TOKEN_CACHE", Mock(is_valid=Mock(return_value=False)))
    monkeypatch.setattr(
        server, "PASSTHROUGH_AUTH_FLAG_SOURCE", Mock(enabled=Mock(return_value=True))
    )
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    handler = object.__new__(server.Handler)
    handler.path = "/v1/chat/completions"
    handler.client_address = ("192.0.2.1", 1234)
    handler.headers = Message()
    handler.headers["Authorization"] = "Bearer known-upstream-key"
    handler.headers["Content-Length"] = "2"
    handler.rfile = Mock()
    handler._send = Mock()
    handler.do_POST()
    handler.rfile.read.assert_not_called()
    assert handler.close_connection
    handler._send.assert_called_once_with(
        401, {"error": {"message": "unauthorized", "type": "auth_error", "code": 401}}
    )


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1", "192.0.2.1"])
@pytest.mark.parametrize("token", [None, "Bearer wrong"])
@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/models/refresh"])
def test_invalid_auth_rejected_before_body_and_budget(monkeypatch, peer, token, path):
    from email.message import Message
    from unittest.mock import Mock

    monkeypatch.setattr(server, "TOKEN_CACHE", Mock(is_valid=Mock(return_value=False)))
    budget = Mock()
    monkeypatch.setattr(server, "_budget", budget)
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    handler = object.__new__(server.Handler)
    handler.path = path
    handler.client_address = (peer, 1234)
    handler.headers = Message()
    if token is not None:
        handler.headers["Authorization"] = token
    handler.headers["Content-Length"] = "2"
    handler.rfile = Mock()
    handler._send = Mock()
    handler.do_POST()
    handler.rfile.read.assert_not_called()
    budget.reserve.assert_not_called()
    assert handler.close_connection
    handler._send.assert_called_once_with(
        401, {"error": {"message": "unauthorized", "type": "auth_error", "code": 401}}
    )


def test_token_cache_missing_or_unreadable_file_fails_closed(tmp_path):
    cache = server.TokenCache(path=tmp_path / "missing", environ={})
    assert not cache.is_valid("anything")
    assert not cache.is_valid("")
    cache = server.TokenCache(path=tmp_path, environ={})
    assert not cache.is_valid("anything")


def test_token_cache_missing_from_start_accepts_env_key(tmp_path):
    cache = server.TokenCache(
        path=tmp_path / "missing", environ={"BRIDGE_KEY": "env-only"}
    )
    assert cache.is_valid("env-only")
    assert not cache.is_valid("anything")


def test_token_cache_file_removed_before_first_check_rejects_env_key(tmp_path):
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=file-key\n", encoding="utf-8")
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "old-key"})
    path.unlink()
    assert not cache.is_valid("old-key")
    assert not cache.is_valid("file-key")


def test_token_cache_utf8_after_rotation_rejects_old_and_new(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=old-key\n")
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "old-key"})
    monkeypatch.setattr(server, "TOKEN_CACHE", cache)

    def _status(token: str) -> int:
        seen: list[int] = []
        handler = _make_bearer_handler(token)
        handler.path = "/v1/models"

        def _fake_send(
            code: int, payload: dict, extra_headers: dict[str, str] | None = None
        ) -> None:
            seen.append(code)

        handler._send = _fake_send
        server.Handler.do_GET(handler)
        assert seen
        return seen[-1]

    assert cache.is_valid("old-key")
    path.write_text("BRIDGE_KEY=new-key-longer\n")
    assert cache.is_valid("new-key-longer")
    assert not cache.is_valid("old-key")
    path.write_bytes(b"\xff")
    assert not cache.is_valid("old-key")
    assert not cache.is_valid("new-key-longer")
    assert _status("old-key") == 401
    assert _status("new-key-longer") == 401


def test_token_cache_unlink_after_seen_rejects_env_old_key(tmp_path, monkeypatch):
    from email.message import Message

    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=old-key\n")
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "old-key"})
    monkeypatch.setattr(server, "TOKEN_CACHE", cache)
    handler = object.__new__(server.Handler)
    handler.headers = Message()
    handler.headers["Authorization"] = "Bearer old-key"
    assert server._auth_ok(handler)
    path.unlink()
    assert not cache.is_valid("old-key")
    assert not server._auth_ok(handler)
    seen: list[int] = []
    http_handler = _make_bearer_handler("old-key")
    http_handler.path = "/v1/models"

    def _fake_send(
        code: int, payload: dict, extra_headers: dict[str, str] | None = None
    ) -> None:
        seen.append(code)

    http_handler._send = _fake_send
    server.Handler.do_GET(http_handler)
    assert seen == [401]


class _CaptureAdapter:
    id = "capture"

    def __init__(self, upstream=None):
        self._upstream_key = upstream
        self.headers = None

    def handle(self, *, path, raw_body, request, headers, sink):
        self.headers = dict(headers)


def _capture_passthrough(monkeypatch, handler, adapter, hub_auth_ok):
    from types import SimpleNamespace

    lease = SimpleNamespace(
        record_success=lambda: None,
        record_failure=lambda: None,
        record_discard=lambda *a: None,
    )
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", "/nonexistent/dynamic_config.json")
    handler._current_lease = lambda: lease
    handler._trace_log_fields = lambda: ""
    handler._trace = None
    handler.path = "/v1/chat/completions"
    monkeypatch.setattr(server, "_log", lambda *a, **k: None)
    monkeypatch.setattr(server, "_strip_passthrough_env", lambda raw, req: (raw, req))
    monkeypatch.setattr(server, "_trace_headers", lambda trace: {})
    monkeypatch.setattr(server, "REQUEST_ATTRIBUTION_ENABLED", False)

    class _Sink:
        def __init__(self, h, extra_headers=None):
            self.status = 200
            self._client_gone_flag = False

    monkeypatch.setattr(server, "_HandlerSink", _Sink)
    handler._serve_passthrough(adapter, b"{}", {}, "m", _hub_auth_ok=hub_auth_ok)
    headers = adapter.headers
    assert headers is not None, "passthrough did not capture headers"
    return headers


def _make_bearer_handler(token, extra=None):
    from email.message import Message

    handler = object.__new__(server.Handler)
    handler.headers = Message()
    handler.headers["Authorization"] = f"Bearer {token}"
    for name, value in (extra or {}).items():
        handler.headers[name] = value
    return handler


def test_passthrough_strips_hub_credentials_with_captured_decision_after_rotation(
    tmp_path, monkeypatch
):
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=old-key\n")
    monkeypatch.setattr(server, "TOKEN_CACHE", server.TokenCache(path=path, environ={}))
    handler = _make_bearer_handler(
        "old-key", {"X-Api-Key": "old-key", "X-Other": "keep"}
    )
    hub_auth_ok = server._auth_ok(handler)
    assert hub_auth_ok
    path.write_text("BRIDGE_KEY=new-key-longer\n")
    assert not server._auth_ok(handler)
    headers = _capture_passthrough(monkeypatch, handler, _CaptureAdapter(), hub_auth_ok)
    assert not ({k.lower() for k in headers} & {"authorization", "x-api-key"})
    assert headers.get("X-Other") == "keep"


def test_passthrough_retains_credentials_for_deferred_or_upstream_key(
    tmp_path, monkeypatch
):
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=hub-key\n")
    monkeypatch.setattr(server, "TOKEN_CACHE", server.TokenCache(path=path, environ={}))
    deferred = _make_bearer_handler("provider-key", {"X-Api-Key": "provider-key"})
    hub_auth_ok = server._auth_ok(deferred)
    assert not hub_auth_ok
    headers = _capture_passthrough(
        monkeypatch, deferred, _CaptureAdapter(), hub_auth_ok
    )
    lowered = {k.lower(): v for k, v in headers.items()}
    assert lowered["authorization"] == "Bearer provider-key"
    assert lowered["x-api-key"] == "provider-key"
    hubbed = _make_bearer_handler("hub-key")
    assert server._auth_ok(hubbed)
    headers = _capture_passthrough(
        monkeypatch, hubbed, _CaptureAdapter(upstream="upstream-key"), True
    )
    assert {k.lower(): v for k, v in headers.items()}[
        "authorization"
    ] == "Bearer hub-key"


def test_token_cache_existing_file_without_bridge_keys_fails_closed(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OTHER_KEY=value\n")
    cache = server.TokenCache(path=path, environ={"DROID_DSH_BRIDGE_KEY": "env-legacy"})
    assert not cache.is_valid("env-legacy")
    assert not cache.is_valid("value")
    assert not cache.is_valid("anything")


def test_token_cache_unreadable_path_without_file_keys_fails_closed(
    tmp_path, monkeypatch
):
    """Unreadable path после наблюдения файла -> fail-closed без env/module."""
    monkeypatch.setattr(server, "AUTH_KEY", "module-auth-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "module-bridge-key")
    cache = server.TokenCache(path=tmp_path, environ={"BRIDGE_KEY": "env-only"})
    assert not cache.is_valid("env-only")
    assert not cache.is_valid("module-auth-key")
    assert not cache.is_valid("module-bridge-key")
    assert not cache.is_valid("wrong-key")
    assert cache._file_keys == ()
    assert cache._file_seen is True
    assert cache._signature is None


def test_token_cache_utf8_corruption_rejects_file_key_and_fails_closed(tmp_path):
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=file-key\n")
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "env-key"}, ttl_s=300)
    assert cache.is_valid("file-key")
    path.write_bytes(b"\xff")
    assert not cache.is_valid("file-key")
    assert not cache.is_valid("env-key")


def test_token_cache_permission_denied_rejects_file_keys_and_fails_closed(tmp_path):
    from unittest.mock import patch

    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=file-key\n")
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "env-key"}, ttl_s=300)
    assert cache.is_valid("file-key")
    path.write_text("BRIDGE_KEY=file-key-longer\n")
    with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
        assert not cache.is_valid("file-key")
        assert not cache.is_valid("file-key-longer")
        assert not cache.is_valid("env-key")


@pytest.mark.parametrize("fail_at", ["stat", "read_text"])
@pytest.mark.parametrize(
    "exc",
    [PermissionError("denied"), OSError("io error")],
    ids=["permission", "oserror"],
)
def test_token_cache_stat_or_read_error_clears_state_immediately(
    tmp_path, monkeypatch, fail_at, exc
):
    from unittest.mock import patch

    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=file-key\n")
    clock = [10.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "env-key"}, ttl_s=300)
    assert cache.is_valid("file-key")
    assert cache._next_check > clock[0]
    if fail_at == "read_text":
        path.write_text("BRIDGE_KEY=file-key-longer\n")
    with patch.object(Path, fail_at, side_effect=exc):
        assert not cache.is_valid("file-key")
        assert not cache.is_valid("env-key")
        assert cache._file_keys == ()
        assert cache._signature is None
        assert cache._next_check == 0.0
        assert cache._file_seen is True


def test_token_cache_chmod_only_change_bypasses_signature_fast_path(
    tmp_path, monkeypatch
):
    import os
    from unittest.mock import patch

    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=file-key\n")
    clock = [10.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "env-key"}, ttl_s=300)
    assert cache.is_valid("file-key")
    before = path.stat()
    try:
        os.chmod(path, 0o000)
        after = path.stat()
        assert (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) == (
            after.st_dev,
            after.st_ino,
            after.st_mtime_ns,
            after.st_size,
        )
        assert before.st_mode != after.st_mode
        with patch.object(
            Path, "read_text", side_effect=PermissionError("denied")
        ) as read_mock:
            assert not cache.is_valid("file-key")
            assert read_mock.called
            assert cache._file_keys == ()
            assert cache._signature is None
            assert cache._next_check == 0.0
            assert cache._file_seen is True
    finally:
        os.chmod(path, 0o600)


def test_token_cache_real_chmod000_revokes_cached_key_without_ttl_expiry(
    tmp_path, monkeypatch
):
    import os

    if os.geteuid() == 0:
        pytest.skip("root can read chmod 000 files")
    path = tmp_path / ".env"
    path.write_text("BRIDGE_KEY=file-key\n")
    clock = [10.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: clock[0])
    cache = server.TokenCache(path=path, environ={"BRIDGE_KEY": "env-key"}, ttl_s=300)
    assert cache.is_valid("file-key")
    try:
        os.chmod(path, 0o000)
        assert not cache.is_valid("file-key")
        assert not cache.is_valid("env-key")
        assert cache._file_keys == ()
        assert cache._signature is None
        assert cache._next_check == 0.0
        assert cache._file_seen is True
    finally:
        os.chmod(path, 0o600)
    assert cache.is_valid("file-key")


def test_non_loopback_invalid_token_rejected_before_body_read(monkeypatch):
    from email.message import Message
    from unittest.mock import Mock

    monkeypatch.setattr(server, "TOKEN_CACHE", Mock(is_valid=Mock(return_value=False)))
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    handler = object.__new__(server.Handler)
    handler.path = "/v1/chat/completions"
    handler.client_address = ("192.0.2.1", 1234)
    handler.headers = Message()
    handler.headers["Authorization"] = "Bearer wrong"
    handler.headers["Content-Length"] = "2"
    handler.rfile = Mock()
    handler._send = Mock()
    handler.do_POST()
    handler.rfile.read.assert_not_called()
    assert handler.close_connection
    assert handler._send.call_args.args[0] == 401


@pytest.mark.parametrize("token", [None, "Bearer wrong"])
def test_invalid_auth_rejected_before_body_and_budget_with_tolerance_flag_enabled(
    monkeypatch, token
):
    from email.message import Message
    from unittest.mock import Mock

    from adapters.passthrough_adapter import PassthroughAdapter
    from core.backend_adapter import AdapterRegistry

    registry = AdapterRegistry()
    registry.register(
        PassthroughAdapter(
            "test",
            {"base_url": "http://127.0.0.1:2455/v1", "api_key": "known-upstream-key"},
            dict,
        )
    )
    monkeypatch.setattr(server, "BACKENDS", registry)
    monkeypatch.setattr(server, "AUTH_KEY", "hub-known-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "hub-known-key")
    monkeypatch.setattr(server, "TOKEN_CACHE", Mock(is_valid=Mock(return_value=False)))
    monkeypatch.setattr(
        server,
        "PASSTHROUGH_AUTH_FLAG_SOURCE",
        Mock(enabled=Mock(return_value=True)),
    )
    budget = Mock()
    monkeypatch.setattr(server, "_budget", budget)
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    handler = object.__new__(server.Handler)
    handler.path = "/v1/chat/completions"
    handler.client_address = ("127.0.0.1", 1234)
    handler.headers = Message()
    if token is not None:
        handler.headers["Authorization"] = token
    handler.headers["Content-Length"] = "2"
    handler.rfile = Mock()
    handler._send = Mock()
    handler.do_POST()
    handler.rfile.read.assert_not_called()
    budget.reserve.assert_not_called()
    assert handler.close_connection
    handler._send.assert_called_once_with(
        401, {"error": {"message": "unauthorized", "type": "auth_error", "code": 401}}
    )


EXEC_LINE = re.compile(
    r"^exec model=(?P<model>\S+) effort=(?P<effort>\S+) effort_source=(?P<source>\S+) "
    r"autonomy=(?P<autonomy>\S+) autonomy_source=(?P<autonomy_source>\S+) "
    r"prompt_bytes=(?P<bytes>\d+) (?P<tag>client=\S+ ua=.*)$"
)
DONE_LINE = re.compile(r"^done model=\S+ rc=\d+ state=\S+ .*client=\S+ ua=.*$")


class TestCatalogClassI(unittest.TestCase):
    """Класс I: структурные нарушения каталога -> отказ старта (fleet_invalid)."""

    def setUp(self):
        self.data = copy.deepcopy(load_raw_fleet())
        self._env = server.ENV_MODEL
        self._probe = server.IMAGE_PROBE
        self._fleet_path = server.FLEET_PATH
        server.ENV_MODEL = ""
        server.IMAGE_PROBE = False
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        server.ENV_MODEL = self._env
        server.IMAGE_PROBE = self._probe
        server.FLEET_PATH = self._fleet_path
        self._tmp.cleanup()

    def _expect(self, reason, model=None):
        with self.assertRaises(server.FleetViolation) as caught:
            server._build_catalog(self.data)
        self.assertEqual(caught.exception.reason, reason)
        if model is not None:
            self.assertEqual(caught.exception.model, model)

    def _bind_confirmed(self, model_id="claude-sonnet-5-5", efforts_proven=None):
        binary = Path(self._tmp.name) / "droid-stand"
        binary.write_bytes(b"stand-droid-binary")
        item = find_model(self.data, model_id)
        item["input"] = ["text", "image"]
        item["images"]["status"] = "confirmed"
        item["images"]["method"] = "workspace-read"
        item["images"]["proof"] = make_proof(
            binary, efforts_proven if efforts_proven is not None else item["efforts"]
        )
        self.data["technical_ref"]["droid_binary_path"] = str(binary)
        return item

    def test_valid_catalogue(self):
        catalog = server._build_catalog(self.data)
        self.assertEqual(catalog["default_model"], "muse-wonder-full-1.0")
        # 3 подписочных droid и 15 моделей остальных бэкендов.
        self.assertEqual(len(catalog["order"]), 18)
        self.assertEqual(
            server._build_catalog(copy.deepcopy(self.data))["schema_version"], 3
        )

    def test_broken_file_refuses_start(self):
        broken = Path(self._tmp.name) / "fleet.json"
        broken.write_text('{"schema_version": 1,', encoding="utf-8")
        server.FLEET_PATH = broken
        with self.assertRaises(SystemExit):
            server._load_fleet()

    def test_duplicate_id(self):
        duplicate = copy.deepcopy(find_model(self.data, "claude-sonnet-5-5"))
        self.data["models"].append(duplicate)
        self._expect("duplicate_id", "claude-sonnet-5-5")

    def test_efforts_off_invalid(self):
        find_model(self.data, "claude-sonnet-5-5")["efforts"] = ["bogus", "high"]
        self._expect("efforts_invalid", "claude-sonnet-5-5")

    def test_default_effort_outside_efforts(self):
        find_model(self.data, "claude-sonnet-5-5")["default_effort"] = "xhigh"
        self._expect("default_effort_invalid", "claude-sonnet-5-5")

    def test_default_model_outside_roster(self):
        self.data["default_model"] = "no-such-model"
        self._expect("default_model_invalid", "-")

    def test_env_model_outside_roster(self):
        server.ENV_MODEL = "kimi-k3"
        self._expect("env_model_invalid", "kimi-k3")

    def test_status_input_inconsistent(self):
        find_model(self.data, "claude-sonnet-5-5")["input"] = ["text", "image"]
        self._expect("status_inconsistent", "claude-sonnet-5-5")

    def test_explicit_unsupported_must_be_unsupported(self):
        m = find_model(self.data, "claude-sonnet-5-5")
        m["images"]["cli_registry"] = "explicit_unsupported"
        m["images"]["status"] = "unverified"
        self._expect("status_inconsistent", "claude-sonnet-5-5")

    def test_confirmed_without_proof(self):
        item = find_model(self.data, "claude-sonnet-5-5")
        item["input"] = ["text", "image"]
        item["images"]["status"] = "confirmed"
        item["images"]["method"] = "workspace-read"
        item["images"]["proof"] = None
        self._expect("confirmed_proof_missing", "claude-sonnet-5-5")

    def test_confirmed_proof_malformed(self):
        item = self._bind_confirmed()
        del item["images"]["proof"]["formats"]
        self._expect("confirmed_proof_malformed", "claude-sonnet-5-5")

    def test_confirmed_efforts_proven_empty(self):
        self._bind_confirmed(efforts_proven=[])
        self._expect("confirmed_efforts_proven_invalid", "claude-sonnet-5-5")

    def test_confirmed_efforts_proven_outside_efforts(self):
        self._bind_confirmed(efforts_proven=["high", "xhigh"])
        self._expect("confirmed_efforts_proven_invalid", "claude-sonnet-5-5")

    def test_confirmed_partial_efforts_proven_starts(self):
        # Класс II: неполный proof — не отказ старта (деградируют только непокрытые effort).
        item = self._bind_confirmed(
            model_id="deepseek-v4.1-flash-free", efforts_proven=["high"]
        )
        catalog = server._build_catalog(self.data)
        self.assertEqual(
            catalog["models"]["deepseek-v4.1-flash-free"]["images"]["proof"][
                "efforts_proven"
            ],
            ["high"],
        )
        self.assertEqual(item["images"]["status"], "confirmed")

    def test_probe_without_flag(self):
        item = find_model(self.data, "gemini-3.8-flash")
        item["input"] = ["text", "image"]
        item["images"]["status"] = "probe"
        item["images"]["method"] = "workspace-read"
        self._expect("probe_flag_missing", "gemini-3.8-flash")

    def test_method_not_implemented(self):
        server.IMAGE_PROBE = True
        item = find_model(self.data, "gemini-3.8-flash")
        item["input"] = ["text", "image"]
        item["images"]["status"] = "probe"
        item["images"]["method"] = "jsonrpc-something"
        self._expect("method_not_implemented", "gemini-3.8-flash")


class TestClampEffortDownward(unittest.TestCase):
    """Helper: downward-first кламп по EFFORT_ORDER, без зависимости от каталога."""

    def test_exact_match_case_insensitive_preserves_allowed(self):
        self.assertEqual(
            server.clamp_effort_downward("HIGH", ["High"], "low"), ("High", False)
        )
        self.assertEqual(
            server.clamp_effort_downward("high", ["max", "high"], "max"),
            ("high", False),
        )

    def test_nearest_lower_wins_over_nearest_upper(self):
        # xhigh: high ниже на 1, max выше на 1 — downward-first выбирает high.
        self.assertEqual(
            server.clamp_effort_downward("xhigh", ["max", "high"], "high"),
            ("high", True),
        )
        self.assertEqual(
            server.clamp_effort_downward("ultra", ["high", "max"], "high"),
            ("max", True),
        )
        self.assertEqual(
            server.clamp_effort_downward("medium", ["high"], "high"), ("high", True)
        )

    def test_upward_fallback_when_no_lower(self):
        self.assertEqual(
            server.clamp_effort_downward("low", ["max", "high"], "max"),
            ("high", True),
        )
        self.assertEqual(
            server.clamp_effort_downward("off", ["high"], "high"), ("high", True)
        )

    def test_unknown_candidate_falls_back_to_default(self):
        self.assertEqual(
            server.clamp_effort_downward("none", ["high"], "high"), ("high", True)
        )
        self.assertEqual(
            server.clamp_effort_downward("bogus", ["low"], "medium"),
            ("medium", True),
        )

    def test_no_rankable_allowed_returns_default(self):
        self.assertEqual(
            server.clamp_effort_downward("high", ["bogus"], "low"), ("low", True)
        )
        self.assertEqual(server.clamp_effort_downward("high", [], "low"), ("low", True))

    def test_exact_match_of_unknown_scale_value(self):
        self.assertEqual(
            server.clamp_effort_downward("custom", ["Custom"], "low"),
            ("Custom", False),
        )


class TestEffortAndModel(BridgeCase):
    """C-02: валидация model/effort до запуска; строковый effort клампится вниз.

    Проверяются фактические параметры RPC initialize_session и исходы в строке
    `exec`; форма конструктора процесса не тестируется (TM-016).
    """

    def setUp(self):
        super().setUp()
        # Обе Gemini проверяются через тот же изолированный FakeDroid-стенд.
        data = droidify_raw_fleet(load_raw_fleet())
        find_model(data, "gemini-4-argon")["backend"] = "droid"
        install_droid_stand(data)

    def _post_logged(self, body):
        """POST и (параметры последней initialize_session, effort_source, autonomy_source)."""
        with self.capture_logs() as lines:
            status, _ = self._post(body, headers={"X-Subagent-Id": "coder-strict"})
        self._last_lines = lines
        execs = [m for m in (EXEC_LINE.match(ln) for ln in lines) if m]
        init = self.hub.inits()[-1]["params"] if self.hub.inits() else None
        source = execs[-1].group("source") if execs else None
        autonomy_source = execs[-1].group("autonomy_source") if execs else None
        return status, init, source, autonomy_source

    def test_defaults_when_model_and_effort_absent(self):
        # Умолчание каталога - muse-wonder-full-1.0 (ADR 0015); сценарий droid-хода фиксирует droid-модель.
        server.MODEL_ID = "claude-sonnet-5-5"  # восстанавливается в BridgeCase.tearDown
        for payload in (
            {},
            {"model": None, "reasoning_effort": None},
            {"model": "", "reasoning_effort": ""},
            {"model": "   ", "reasoning_effort": "   "},
        ):
            status, init, source, _ = self._post_logged(chat_body(**payload))
            self.assertEqual(status, 200)
            self.assertEqual(init["modelId"], "claude-sonnet-5-5")
            self.assertEqual(init["reasoningEffort"], "high")
            self.assertEqual(source, "default")

    def test_allowed_efforts_accepted(self):
        # Уровни подписочных моделей — строго из согласованного каталога.
        wanted = {
            "claude-sonnet-5-5": ["low", "medium", "high", "max"],
            "gemini-3.8-flash": ["low", "medium", "high"],
            "gemini-4-argon": ["low", "medium", "high"],
            "deepseek-v4.1-flash": ["off", "low", "medium", "high"],
        }
        for model, efforts in wanted.items():
            self.assertEqual(server.FLEET["models"][model]["efforts"], efforts, model)
            for effort in efforts:
                status, init, source, _ = self._post_logged(
                    chat_body(model=model, effort=effort)
                )
                self.assertEqual(status, 200, (model, effort))
                self.assertEqual(init["modelId"], model)
                self.assertEqual(init["reasoningEffort"], effort)
                self.assertEqual(source, "request")
        # За пределами каталога строковый effort не отказ, а кламп вниз до high.
        status, init, source, _ = self._post_logged(
            chat_body(model="claude-sonnet-5-5", effort="xhigh")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["reasoningEffort"], "high")
        self.assertEqual(source, "request")

    def test_outside_catalog_efforts_clamped(self):
        # (model, запрошенный effort, ожидаемый effective effort)
        cases = [
            ("claude-sonnet-5-5", "xhigh", "high"),  # nearest lower
            ("claude-sonnet-5-5", "max", "max"),  # exact allowed
            ("claude-sonnet-5-5", "max\n", "max"),  # strip до проверки
            ("gemini-3.8-flash", "medium", "medium"),  # exact allowed effort
            ("gemini-4-argon", "minimal", "low"),
            ("gemini-4-argon", "xhigh", "high"),
            ("claude-sonnet-5-5", "HIGH", "high"),  # case-insensitive exact
            ("claude-sonnet-5-5", "off", "low"),  # нет нижнего -> upward
            ("claude-sonnet-5-5", "none", "high"),  # unknown -> default (high)
            ("deepseek-v4.1-flash", "off", "off"),  # отключённый reasoning допустим
            ("deepseek-v4.1-flash", "xhigh", "high"),  # lower high, не upper max
            ("deepseek-v4.1-flash", "ultra", "high"),  # nearest lower
        ]
        for model, effort, expected in cases:
            before_inits = len(self.hub.inits())
            status, init, source, _ = self._post_logged(
                chat_body(model=model, effort=effort)
            )
            self.assertEqual(status, 200, (model, effort))
            self.assertEqual(init["modelId"], model)
            self.assertEqual(init["reasoningEffort"], expected, (model, effort))
            self.assertEqual(source, "request", (model, effort))
            self.assertGreater(len(self.hub.inits()), before_inits)
        # Кламп пишется в лог только при фактическом клампе.
        status, init, source, _ = self._post_logged(
            chat_body(model="claude-sonnet-5-5", effort="xhigh")
        )
        self.assertEqual(status, 200)
        self.assertIn(
            "clamp reasoning_effort 'xhigh' -> 'high' for model claude-sonnet-5-5",
            self._last_lines,
        )
        status, init, source, _ = self._post_logged(
            chat_body(model="claude-sonnet-5-5", effort="HIGH")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["reasoningEffort"], "high")
        self.assertFalse(
            any(ln.startswith("clamp reasoning_effort") for ln in self._last_lines)
        )

    def test_nonstring_effort_rejected(self):
        for bad in (5, ["high"], {"level": "high"}, True):
            before = len(self.hub.spawns())
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", effort=bad)
            )
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"]["type"], "unsupported_reasoning_effort")
            self.assertEqual(
                body["error"]["message"], "reasoning_effort must be a string"
            )
            self.assertEqual(len(self.hub.spawns()), before)

    def test_models_outside_fleet_rejected(self):
        cases = [
            "Claude-Sonnet-5-5",
            "kimi-k3",
            "nonexistent-model-xyz",
            "x\nexec model=claude-sonnet-5-5 effort=high effort_source=request",
            "sk-SECRET-0123456789abcdef",
            "A" * 5000,
        ]
        for model in cases:
            before = len(self.hub.spawns())
            status, body = self._post_json(chat_body(model=model))
            self.assertEqual(status, 404, model[:20])
            self.assertEqual(body["error"]["type"], "model_not_found")
            self.assertEqual(len(self.hub.spawns()), before)
        for bad in (5, ["claude-sonnet-5-5"], {"id": "claude-sonnet-5-5"}, True):
            status, body = self._post_json(chat_body(model=bad))
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["type"], "model_not_allowed")

    def test_model_and_effort_are_stripped(self):
        status, init, source, _ = self._post_logged(
            chat_body(model=" claude-sonnet-5-5 ", effort=" high ")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["modelId"], "claude-sonnet-5-5")
        self.assertEqual(init["reasoningEffort"], "high")
        self.assertEqual(source, "request")

    def test_autonomy_default_is_off(self):
        status, init, _, autonomy_source = self._post_logged(
            chat_body(model="claude-sonnet-5-5")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["autonomyLevel"], "off")
        self.assertEqual(autonomy_source, "default")

    def test_autonomy_levels_accepted(self):
        changes = pytest.MonkeyPatch()
        changes.setenv("DROID_ALLOW_HIGH_AUTONOMY", "1")
        self.addCleanup(changes.undo)
        for level in ("low", "medium", "high", "off"):
            status, init, _, autonomy_source = self._post_logged(
                chat_body(model="deepseek-v4.1-flash", effort="max", autonomy=level)
            )
            self.assertEqual(status, 200, level)
            self.assertEqual(
                init["autonomyLevel"], level
            )  # off задаётся RPC, не опущенным флагом
            self.assertEqual(autonomy_source, "request")
        status, init, _, autonomy_source = self._post_logged(
            chat_body(model="gemini-3.8-flash", autonomy=" low ")
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["autonomyLevel"], "low")
        self.assertEqual(autonomy_source, "request")

    def test_autonomy_bad_rejected(self):
        for bad in ("ultra", "HIGH", "none", "skip", "high\nx"):
            before = len(self.hub.spawns())
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", autonomy=bad)
            )
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"]["type"], "unsupported_autonomy")
            self.assertEqual(len(self.hub.spawns()), before)
        for bad in (5, ["high"], {"level": "high"}, True):
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", autonomy=bad)
            )
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["type"], "unsupported_autonomy")

    def test_reasoning_object_rejected(self):
        before = len(self.hub.spawns())
        status, body = self._post_json(
            chat_body(model="claude-sonnet-5-5", reasoning={"effort": "high"})
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "unsupported_parameter")
        self.assertEqual(len(self.hub.spawns()), before)
        # reasoning-валидация независима от клампа строкового effort.
        status, body = self._post_json(
            chat_body(
                model="claude-sonnet-5-5",
                effort="max",
                reasoning={"effort": "high"},
            )
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "unsupported_parameter")
        self.assertEqual(len(self.hub.spawns()), before)

    def test_stream_with_clamped_effort_succeeds(self):
        status, init, source, _ = self._post_logged(
            chat_body(model="claude-sonnet-5-5", effort="xhigh", stream=True)
        )
        self.assertEqual(status, 200)
        self.assertEqual(init["reasoningEffort"], "high")
        self.assertEqual(source, "request")

    def test_launcher_missing_gives_503_and_no_spawn(self):
        server.LAUNCHER = str(Path(self._tmp.name) / "no-such-launcher.sh")
        before = len(self.hub.spawns())
        status, body = self._post_json(chat_body(model="claude-sonnet-5-5"))
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertEqual(body["error"]["code"], 503)
        self.assertEqual(len(self.hub.spawns()), before)


class TestHealthAndModels(BridgeCase):
    def test_health_exactly_seven_keys(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(
            sorted(body),
            sorted(
                [
                    "ok",
                    "transport",
                    "model",
                    "active",
                    "max_concurrent",
                    "tool_emulation",
                    "uptime_s",
                ]
            ),
        )
        self.assertNotIn("default_auto", body)

    def test_models_list(self):
        status, body = self._get("/v1/models")
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "list")
        # 18 моделей каталога + legacy-моки стенда FakeDroid (grok-4.7, glm-5.3, deepseek-v4.1-flash).
        self.assertEqual(len(body["data"]), 18 + len(_DROID_LEGACY_MODELS))
        self.assertTrue(
            {"gpt-6.1-terra", "gpt-6.1-sol"} <= {e["id"] for e in body["data"]}
        )
        self.assertIn("muse-wonder-full-1.0", {e["id"] for e in body["data"]})
        self.assertEqual(
            body["data"][0]["id"], "muse-wonder-full-1.0"
        )  # умолчание каталога первым
        self.assertIn("claude-sonnet-5-5", {e["id"] for e in body["data"]})
        expected_keys = sorted(
            [
                "available",
                "context_length",
                "context_window",
                "created",
                "default_reasoning_effort",
                "id",
                "max_output_tokens",
                "modalities",
                "object",
                "owned_by",
                "penalized_until",
                "supported_reasoning_efforts",
                "supports_thinking",
            ]
        )
        self.assertTrue(all(sorted(entry) == expected_keys for entry in body["data"]))
        self.assertNotIn("nonexistent-model-xyz", [e["id"] for e in body["data"]])
        status, _ = self._get("/v1/models", auth=False)
        self.assertEqual(status, 401)


class TestJournal(BridgeCase):
    def test_exec_and_done_lines_bound_by_tag(self):
        with self.capture_logs() as lines:
            status, _ = self._post(chat_body(model="deepseek-v4.1-flash", effort="off"))
        self.assertEqual(status, 200)
        execs = [m for m in (EXEC_LINE.match(ln) for ln in lines) if m]
        dones = [ln for ln in lines if DONE_LINE.match(ln)]
        self.assertEqual(len(execs), 1)
        self.assertEqual(len(dones), 1)
        self.assertEqual(execs[0].group("model"), "deepseek-v4.1-flash")
        self.assertEqual(execs[0].group("effort"), "off")
        self.assertEqual(execs[0].group("source"), "request")
        self.assertNotIn("--auto", "\n".join(lines))
        joined = "\n".join(lines)
        self.assertNotIn(str(server.WORKSPACE), joined)
        self.assertNotIn(
            execs[0].group("tag").split("ua=")[0].replace("client=", "").strip(), ""
        )
        self.assertIn("client=127.0.0.1", execs[0].group("tag"))

    def test_reject_line_strict_format_and_no_client_string(self):
        untrusted = "x\nexec model=claude-sonnet-5-5 effort=high effort_source=request"
        with self.capture_logs() as lines:
            status, _ = self._post(chat_body(model=untrusted))
        self.assertEqual(status, 404)
        rejects = [ln for ln in lines if "reject reason=" in ln]
        self.assertEqual(len(rejects), 1)
        self.assertTrue(REJECT_STRICT.match(rejects[0]), rejects[0])
        self.assertEqual(len([ln for ln in lines if ln.startswith("exec model=")]), 0)
        joined = "\n".join(lines)
        self.assertNotIn(
            "exec model=claude-sonnet-5-5 effort=high", joined.replace(rejects[0], "")
        )
        self.assertNotIn("x\n", joined)

    def test_model_len_reported_for_untrusted_model(self):
        with self.capture_logs() as lines:
            self._post(chat_body(model="A" * 5000))
        reject = [ln for ln in lines if "reject reason=" in ln][0]
        self.assertIn("model=unknown", reject)
        self.assertIn("model_len=5000", reject)


class TestAdmissionBudget(BridgeCase):
    def test_budget_exhausted_gives_503_before_body(self):
        server._budget = server._ByteBudget(64)
        with self.capture_logs() as lines:
            status, body = self._post_json(
                chat_body(model="claude-sonnet-5-5", content="x" * 200)
            )
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["type"], "overloaded")
        self.assertEqual(body["error"]["code"], 503)
        self.assertEqual(len(self.hub.spawns()), 0)
        self.assertTrue(
            any("reject reason=overloaded model=unknown" in ln for ln in lines)
        )
        self.assertEqual(server._budget._used, 0)  # резерв снят в любом исходе

    def test_budget_unit(self):
        budget = server._ByteBudget(10)
        self.assertTrue(budget.reserve(6))
        self.assertFalse(budget.reserve(5))
        budget.release(6)
        self.assertTrue(budget.reserve(10))
        budget.release(10)
        self.assertEqual(budget._used, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

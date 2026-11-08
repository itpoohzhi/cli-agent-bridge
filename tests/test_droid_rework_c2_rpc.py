"""Регрессии fail-closed RPC-политики C2."""

from __future__ import annotations

import queue
import threading
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

import server


def test_flag_readback_preserves_order_and_allows_missing_fields() -> None:
    server.Run._check_flags({})
    with pytest.raises(server.RpcError, match="disableBuiltinSkills"):
        server.Run._check_flags(
            {"disableBuiltinSkills": False, "autoRejectPermissionRequests": False}
        )


@pytest.mark.parametrize(
    "flag", ["autoRejectPermissionRequests", "disableBuiltinSkills"]
)
@pytest.mark.parametrize("value", [False, 0, 1, None, "true"])
def test_security_flag_readback_fails_closed(flag: str, value: object) -> None:
    with pytest.raises(server.RpcError, match=flag):
        server.Run._check_flags({flag: value})


@pytest.mark.parametrize(
    "method",
    [
        "droid.request_permission",
        "permission_request",
        "request_permission",
        "droid.session_notification",
    ],
)
def test_incoming_permission_request_aborts_rpc(method: str) -> None:
    proc = object.__new__(server.RpcProcess)
    proc.protocol_version = ""
    proc.server_requests = 0
    proc.inbox = queue.Queue()
    proc.inbox_bytes = 0
    proc._inbox_lock = threading.Lock()
    proc.overflowed = False
    proc._respond = Mock()
    proc.notify = Mock(return_value="r1")
    frame = {
        "method": method,
        "params": {"notification": {"type": "permission_request"}},
    }
    if method != "droid.session_notification":
        frame["id"] = "permission-1"
    proc._on_message(frame)
    proc._respond.assert_not_called()
    with pytest.raises(server.RpcPermissionDenied, match="permission"):
        proc.call("droid.add_user_message", {}, timeout=0.05)


@pytest.mark.parametrize("kind", ["permission_request", "request_permission"])
def test_permission_notification_aborts_run(kind: str) -> None:
    run = object.__new__(server.Run)
    run.sid = "sid"
    run.armed = True
    with pytest.raises(server.RpcError, match="permission"):
        run._on_notif({"sessionId": "sid", "notification": {"type": kind}})


def test_permission_during_restore_never_falls_back_to_replay() -> None:
    run = object.__new__(server.Run)
    run.plan = {"sid": "sid", "hash8": "hash"}
    run.cancel = threading.Event()

    def denied(*args: object) -> None:
        raise server.RpcPermissionDenied("permission request forbidden")

    with pytest.raises(server.RpcError, match="permission"):
        run._load(cast(server.RpcProcess, cast(object, SimpleNamespace(call=denied))))

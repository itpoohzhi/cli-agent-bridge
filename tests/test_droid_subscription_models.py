"""Регрессии адресного реворка C23: HTTP, DTO и реальные группы RPC-процессов."""

from __future__ import annotations

import dataclasses
import json
import os
import queue
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

import server
from core import gateway_execution_policy as policy
from tests.bridge_testlib import pid_alive, wait_until
from tests.rpc_testlib import RpcCase
from tests.test_request_attribution import route as route
from tools import droid_image, droid_probe_config, receipt_schema


@pytest.fixture
def cli_route(
    monkeypatch: pytest.MonkeyPatch, route: Callable[..., Any]
) -> Callable[..., Any]:
    for backend in ("droid", "muse"):
        monkeypatch.setattr(
            server.BACKENDS.get(backend), "preflight", lambda: (True, "")
        )
    monkeypatch.setattr(server.Handler, "_serve_json", Mock())
    monkeypatch.setattr(server.Handler, "_prompt_guard", lambda *_: (0, "-", 0))
    monkeypatch.setattr(server.Handler, "_context_gate", lambda _, req, *a: (req, None))
    monkeypatch.setattr(server, "_is_detached_enabled", lambda: False)
    monkeypatch.delenv("DROID_ALLOW_HIGH_AUTONOMY", raising=False)
    monkeypatch.delenv("DROID_MUTATING_SUBAGENT_PREFIXES", raising=False)
    return route


def test_muse_is_not_subject_to_droid_policy(cli_route: Callable[..., Any]) -> None:
    handler = cli_route(
        {
            "model": "muse-wonder-full-1.0",
            "autonomy": "high",
            "messages": [{"role": "user", "content": "hello"}],
        },
        {"X-Subagent-Id": "panel-judge-k1"},
    )
    handler._send.assert_not_called()
    handler._serve_json.assert_called_once()
    assert handler._serve_json.call_args.args[0]["autonomy"] == "high"


@pytest.mark.parametrize("autonomy", ["low", "medium"])
@pytest.mark.parametrize(
    "identity", [None, "", "explorer-1", "reviewer-1", "skeptic-1", "verifier-1"]
)
def test_mutating_http_requires_coder(
    cli_route: Callable[..., Any], autonomy: str, identity: str | None
) -> None:
    handler = cli_route(
        {
            "model": "gpt-6.1-sol",
            "autonomy": autonomy,
            "subagent_id": "coder-body-cannot-authorize",
            "extra_body": {"subagent_id": "coder-extra-cannot-authorize"},
        },
        {} if identity is None else {"X-Subagent-Id": identity},
    )
    assert handler._send.call_args.args[0] in (400, 403)
    assert handler._send.call_args.args[1]["error"]["type"] == "autonomy_role_forbidden"
    handler._serve_json.assert_not_called()


@pytest.mark.parametrize("autonomy", ["low", "medium"])
def test_mutating_http_accepts_coder(
    cli_route: Callable[..., Any], autonomy: str
) -> None:
    handler = cli_route(
        {"model": "gpt-6.1-sol", "autonomy": autonomy},
        {"X-Subagent-Id": "coder-1"},
    )
    handler._send.assert_not_called()
    assert handler._serve_json.call_args.args[0]["autonomy"] == autonomy


def test_autonomy_decision_is_frozen_and_wrapper_returns_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DROID_DEFAULT_AUTONOMY", raising=False)
    decision = policy.resolve_autonomy_decision(
        "medium", "DROID", subagent_id="coder-1"
    )
    assert dataclasses.is_dataclass(decision)
    assert (decision.value, decision.source) == ("medium", "request")
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(decision, "value", "high")
    assert policy.resolve_autonomy("medium", "DROID", subagent_id="coder-1") == "medium"
    assert policy.resolve_autonomy_decision(None, "DROID").source == "default"


@pytest.mark.parametrize(
    "frame",
    [
        {"method": "permission_request"},
        {
            "method": "droid.session_notification",
            "params": {"notification": {"type": "permission_request"}},
        },
    ],
)
def test_wait_settings_rejects_permission_before_readback(
    frame: dict[str, object],
) -> None:
    rpc = object.__new__(droid_image._Rpc)
    rpc.inbox = queue.Queue()
    rpc.inbox.put(frame)
    rpc.inbox.put(
        {"params": {"notification": {"type": "settings_updated", "settings": {}}}}
    )
    with pytest.raises(RuntimeError, match="permission request during settings update"):
        rpc.wait_settings()


def test_probe_targets_preserve_multiple_efforts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fleet = tmp_path / "fleet.json"
    fleet.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "model",
                        "backend": "droid",
                        "efforts": ["low", "high"],
                        "default_effort": "high",
                    }
                ]
            }
        )
    )
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", "model:low,model:high,model:low")
    targets = droid_probe_config.load_droid_probe_targets(fleet)
    assert {(t.model, t.effort) for t in targets} == {
        ("model", "high"),
        ("model", "low"),
    }
    assert len(targets) == 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(targets[0], "effort", "medium")


def test_image_script_from_foreign_cwd_and_single_schema(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(Path(droid_image.__file__).resolve()), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )
    assert result.returncode == 0, result.stderr
    assert "--source" in result.stdout
    assert droid_image.schema is receipt_schema
    assert "receipt_schema" not in sys.modules


@pytest.fixture
def rpc_case() -> Iterator[Any]:
    case = RpcCase()
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()
        case.doCleanups()


def _write_permission_launcher(launcher: Path) -> None:
    # Расширяется только тестовый процесс, а не код адаптера или вендора.
    launcher.write_text(
        f"#!{sys.executable}\n"
        f"import sys\nsys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        "import os, signal, subprocess, fake_droid\n"
        "original = fake_droid.Fake.handle\n"
        "def handle(self, req):\n"
        "    if req.get('method') == 'droid.initialize_session':\n"
        "        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "        self.log({'ev': 'owned_child', 'child': child.pid})\n"
        "        def stop(*_):\n"
        "            child.wait(timeout=2)\n"
        "            signal.signal(signal.SIGTERM, signal.SIG_DFL)\n"
        "            os.kill(os.getpid(), signal.SIGTERM)\n"
        "        signal.signal(signal.SIGTERM, stop)\n"
        "        if self.config().get('permission_on_init'):\n"
        "            self.emit({'method': 'permission_request', 'id': 'permission-init'})\n"
        "            return\n"
        "    return original(self, req)\n"
        "fake_droid.Fake.handle = handle\n"
        "fake_droid.main(sys.argv[1:])\n"
    )


@pytest.mark.parametrize("stage", ["spawn", "resident"])
@pytest.mark.parametrize(
    "model",
    [
        "claude-sonnet-5-5",
        "gemini-3.8-flash",
        "gpt-6.1-sol",
    ],
)
def test_permission_abort_kills_group_and_prevents_reuse(
    rpc_case: Any,
    stage: str,
    model: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = rpc_case
    _write_permission_launcher(case.hub.launcher)
    monkeypatch.setattr(server, "_is_detached_enabled", lambda: False)
    conv = case.conv("permission-chat", model=model)
    if stage == "spawn":
        case.hub.configure(permission_on_init=True)
    else:
        assert conv.ask("first")[0] == 200
        case.hub.script(
            [
                {
                    "steps": [
                        {"op": "notify", "type": "permission_request"},
                        {"op": "hang"},
                    ]
                }
            ]
        )
    with case.capture_logs() as logs:
        status, body = conv.ask("forbidden")
    assert status == 502, body
    assert any("err='permission request forbidden by bridge'" in line for line in logs)
    spawned = case.hub.spawns()[-1]["pid"]
    children = [r["child"] for r in case.hub.records() if r["ev"] == "owned_child"]
    _assert_permission_cleanup(case, spawned, children)
    case.hub.configure(permission_on_init=False)
    assert conv.ask("retry safely")[0] == 200
    assert case.chat_of("permission-chat").proc.pid != spawned


def _assert_permission_cleanup(case: Any, spawned: int, children: list[int]) -> None:
    assert children
    assert wait_until(
        lambda: server.POOL.used == 0 and not server._rpc_procs, timeout=5
    )
    assert not pid_alive(spawned)
    assert all(not pid_alive(child) for child in children)
    with pytest.raises(ProcessLookupError):
        os.killpg(spawned, 0)
    chat = case.chat_of("permission-chat")
    assert chat.proc is None and chat.state == "DIRTY"


@pytest.mark.parametrize(
    "identity,expected", [(None, 400), ("explorer-1", 400), ("coder-1", 200)]
)
def test_wire_mutation_role(
    rpc_case: Any,
    identity: str | None,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DROID_REQUIRE_SUBAGENT_FOR_MUTATION", "0")
    monkeypatch.setenv("DROID_MUTATING_SUBAGENT_PREFIXES", "coder-")
    status, body = rpc_case._post_json(
        {
            "model": "gpt-6.1-sol",
            "autonomy": "medium",
            "messages": [{"role": "user", "content": "hello"}],
        },
        headers={} if identity is None else {"X-Subagent-Id": identity},
    )
    assert status == expected, body
    if expected == 200:
        assert rpc_case.hub.inits()[0]["params"]["autonomyLevel"] == "medium"
    else:
        assert body["error"]["type"] == "autonomy_role_forbidden"
        assert not rpc_case.hub.spawns()

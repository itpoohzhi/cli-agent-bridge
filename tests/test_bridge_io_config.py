"""Регрессии Cycle 2: admission, настройки принятых сокетов и keepalive."""

from __future__ import annotations

import ast
import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import bridge_io_config, http_accept  # noqa: E402


def test_admission_budget_import_compatibility() -> None:
    assert bridge_io_config.AdmissionBudget is http_accept.AdmissionBudget


def test_concurrent_admission_preserves_limit_and_releases() -> None:
    budget = http_accept.AdmissionBudget(
        bridge_io_config.BridgeIOConfig(
            admission_limit=4, ui_reserve=0, header_headroom=0
        )
    )
    gate = Barrier(16)

    def acquire(index: int) -> bool:
        gate.wait(timeout=5.0)
        return budget.acquire(str(index))

    with ThreadPoolExecutor(max_workers=16) as pool:
        accepted = list(pool.map(acquire, range(16)))
        assert sum(accepted) == 4
        list(pool.map(budget.release, map(str, range(16))))
    assert budget._tickets == {}
    assert budget.acquire("next")
    budget.release("next")
    budget.release("next")


def test_admission_rolls_back_ticket_on_insertion_exception() -> None:
    class FailingTickets(dict[str, tuple[bool, bool]]):
        def __setitem__(self, key: str, value: tuple[bool, bool]) -> None:
            super().__setitem__(key, value)
            raise RuntimeError("insertion failed")

    budget = http_accept.AdmissionBudget()
    budget._tickets = FailingTickets()
    with pytest.raises(RuntimeError, match="insertion failed"):
        budget.acquire("failed", is_ui=True)
    assert budget._tickets == {}
    assert (budget._ui_count, budget._header_count) == (0, 0)
    assert budget._lock.acquire(blocking=False)
    budget._lock.release()


def test_admission_reserves_and_duplicate_release() -> None:
    budget = http_accept.AdmissionBudget(
        bridge_io_config.BridgeIOConfig(
            admission_limit=3, ui_reserve=1, header_headroom=1
        )
    )
    assert budget.acquire("regular")
    assert budget.acquire("regular", is_ui=True)
    assert not budget.acquire("overflow")
    assert budget.acquire("ui", is_ui=True)
    assert budget.acquire("header", is_header=True)
    with pytest.raises(ValueError):
        budget.acquire("invalid", is_ui=True, is_header=True)
    for ticket in ("ui", "ui", "header", "regular"):
        budget.release(ticket)
    assert budget._tickets == {}
    assert (budget._ui_count, budget._header_count) == (0, 0)


@pytest.mark.parametrize("nodelay", [True, False])
def test_socket_keepalive_is_independent_of_nodelay(nodelay: bool) -> None:
    with socket.socket() as sock:
        http_accept.configure_accepted_socket(
            sock, bridge_io_config.BridgeIOConfig(tcp_nodelay=nodelay)
        )
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
        assert bool(sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)) is nodelay


@pytest.mark.parametrize(
    ("read_timeout", "write_timeout", "expected"),
    [(None, None, 9.0), (2.5, None, 2.5), (None, 3.5, 3.5), (5.0, 1.5, 1.5)],
)
def test_configured_socket_timeout(
    read_timeout: float | None, write_timeout: float | None, expected: float
) -> None:
    with socket.socket() as sock:
        sock.settimeout(9.0)
        http_accept.configure_accepted_socket(
            sock,
            bridge_io_config.BridgeIOConfig(
                read_timeout_s=read_timeout, write_timeout_s=write_timeout
            ),
        )
        assert sock.gettimeout() == expected


def test_socket_timeouts_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_READ_TIMEOUT_S", "4.5")
    monkeypatch.setenv("BRIDGE_WRITE_TIMEOUT_S", "2.5")
    config = bridge_io_config.load_bridge_io_config()
    assert (config.read_timeout_s, config.write_timeout_s) == (4.5, 2.5)
    with socket.socket() as sock:
        http_accept.configure_accepted_socket(sock)
        assert sock.gettimeout() == 2.5


def test_server_accept_and_handler_setup_apply_socket_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import server

    monkeypatch.setenv("BRIDGE_READ_TIMEOUT_S", "4.5")
    monkeypatch.setenv("BRIDGE_WRITE_TIMEOUT_S", "2.5")
    with server.Server(("127.0.0.1", 0), server.Handler) as httpd:
        httpd.socket.settimeout(2.0)
        with socket.create_connection(httpd.server_address, timeout=2.0):
            accepted, address = httpd.get_request()
            with accepted:
                assert accepted.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
                assert accepted.gettimeout() == 2.5
                handler = server.Handler.__new__(server.Handler)
                handler.request = accepted
                handler.client_address = address
                handler.server = httpd
                handler.setup()
                try:
                    assert (
                        accepted.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
                    )
                    assert accepted.gettimeout() == 2.5
                finally:
                    handler.finish()


@pytest.mark.parametrize("field", ["read_timeout_s", "write_timeout_s"])
@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_socket_timeout_is_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        bridge_io_config.BridgeIOConfig(**{field: value})


@pytest.mark.parametrize("override", [None, "17.5"])
def test_server_keepalive_default_and_env(
    monkeypatch: pytest.MonkeyPatch, override: str | None
) -> None:
    path = Path(__file__).resolve().parents[1] / "server.py"
    tree = ast.parse(path.read_text())
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "KEEPALIVE_S" for t in node.targets)
    )
    monkeypatch.delenv("BRIDGE_KEEPALIVE_S", raising=False)
    if override is not None:
        monkeypatch.setenv("BRIDGE_KEEPALIVE_S", override)
    helpers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_bridge_env"
    ]
    namespace = {"os": os}
    exec(
        compile(
            ast.Module(body=[*helpers, assignment], type_ignores=[]), str(path), "exec"
        ),
        namespace,
    )
    assert namespace["KEEPALIVE_S"] == (10.0 if override is None else 17.5)

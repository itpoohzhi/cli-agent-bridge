"""Endpoint routing boundaries: no DNS, remote probes or route mutations."""

import subprocess
from unittest.mock import Mock

import pytest

from tools import system_proxy_zombie_guard as guard


@pytest.mark.parametrize("value,port", [
    ("localhost:44445", 44445),
    ("127.0.0.1:10816", 10816),
    ("http://localhost:10817", 10817),
    ("https://127.0.0.1:10820/", 10820),
    ("socks://localhost:44445", 44445),
    ("socks5://localhost:10816", 10816),
    ("socks5h://localhost:10817", 10817),
    ("HTTP://LOCALHOST:44445", 44445),
])
def test_owned_endpoints_route_to_numeric_ipv4_loopback(value, port):
    assert guard.parse_endpoint(value) == guard.Endpoint("127.0.0.1", port)


@pytest.mark.parametrize("value,port", [
    ("[::1]:44445", 44445),
    ("http://[::1]:44445", 44445),
    ("https://[::1]:10816/", 10816),
    ("socks5://[::1]:10817", 10817),
    ("socks5h://[::1]:10820", 10820),
])
def test_owned_endpoints_route_to_numeric_ipv6_loopback(value, port):
    assert guard.parse_endpoint(value) == guard.Endpoint("::1", port)


@pytest.mark.parametrize("value", [
    None, "", "localhost", "localhost:", ":44445",
    "http://localhost", "http://localhost:444450",
    "http://localhost:044445", "http://localhost:+44445",
    "http://localhost:４４４４５", "http://localhost:0",
    "http://localhost:10821", "http://localhost:10822",
    "http://[::1]:10821", "http://[::1]:10822",
    "ftp://localhost:44445", "file://localhost:44445",
    "http://127.0.0.2:44445", "http://127.1:44445",
    "http://2130706433:44445", "http://0.0.0.0:44445",
    "http://[::2]:44445", "http://[::ffff:127.0.0.1]:44445",
    "http://localhost.:44445", "http://localhost.example:44445",
    "http://proxy.example:44445", "http://192.168.1.1:44445",
    "http://localhost:44445/path", "http://localhost:44445//",
    "http://localhost:44445?x=1", "http://localhost:44445#fragment",
    "http://user@localhost:44445", "http://localhost:44445@evil.example",
    "http://localhost\\:44445", "http://%6cocalhost:44445",
    " http://localhost:44445", "http://localhost:44445 ",
    "http://localhost:44445\n", "http://localhost:\t44445",
    "http://localhost:44445\0",
])
def test_ambiguous_or_unowned_routes_are_rejected(value):
    assert guard.parse_endpoint(value) is None


@pytest.mark.parametrize("host,family", [
    ("127.0.0.1", guard.socket.AF_INET),
    ("::1", guard.socket.AF_INET6),
])
def test_tcp_probe_uses_literal_loopback_and_never_resolves_dns(
    monkeypatch, host, family,
):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=connection)
    resolver = Mock(side_effect=AssertionError("DNS must not be used"))
    monkeypatch.setattr(guard.socket, "socket", factory)
    monkeypatch.setattr(guard.socket, "getaddrinfo", resolver)

    assert guard.tcp_probe(host, 44445, 0.2) is True

    factory.assert_called_once_with(family, guard.socket.SOCK_STREAM)
    connection.settimeout.assert_called_once_with(0.2)
    connection.connect.assert_called_once_with((host, 44445))
    resolver.assert_not_called()


@pytest.mark.parametrize("exception,expected", [
    (ConnectionRefusedError(), False),
    (TimeoutError(), False),
    (PermissionError(), None),
    (OSError("indeterminate"), None),
])
def test_tcp_probe_distinguishes_failure_from_unknown(
    monkeypatch, exception, expected
):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.connect.side_effect = exception
    monkeypatch.setattr(guard.socket, "socket", Mock(return_value=connection))

    assert guard.tcp_probe("127.0.0.1", 10820, 0.1) is expected


def test_remote_tcp_probe_is_rejected_before_socket_creation(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(guard.socket, "socket", factory)

    with pytest.raises(ValueError):
        guard.tcp_probe("proxy.example", 44445, 0.2)

    factory.assert_not_called()


@pytest.mark.parametrize("returncode,stdout,stderr,expected", [
    (1, "", "", 0),
    (0, "p123\n", "", 1),
    (0, "p123\nf4\np123\nf5\np456\n", "", 2),
    (0, "", "", None),
    (0, "malformed\n", "", None),
    (0, "p0\n", "", None),
    (1, "p123\n", "", None),
    (2, "", "", None),
    (1, "", "permission denied", None),
    (0, "p123\n", "incomplete listing", None),
])
def test_listener_observation_is_fail_closed(
    returncode, stdout, stderr, expected
):
    runner = Mock(return_value=subprocess.CompletedProcess(
        [], returncode, stdout, stderr
    ))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    observed = system.listener_count(44445, guard.Budget(24, lambda: 0))

    assert observed == expected
    arguments = runner.call_args.args[0]
    assert arguments == [
        guard.LSOF, "-nP", "-a", "-iTCP:44445",
        "-sTCP:LISTEN", "-F", "p",
    ]
    # No IPv4-only selector: an IPv6 listener must also block cleanup.
    assert "-i4" not in arguments
    assert "-iTCP@127.0.0.1:44445" not in arguments


@pytest.mark.parametrize("method", ["listener_count", "probe"])
@pytest.mark.parametrize("port", [10821, 10822])
def test_backend_refuses_unowned_ports(method, port):
    runner = Mock()
    connector = Mock()
    system = guard.System(
        guard.Config(), runner=runner, connector=connector, lock=Mock()
    )

    with pytest.raises(guard.GuardError):
        getattr(system, method)(port, guard.Budget(24, lambda: 0))

    runner.assert_not_called()
    connector.assert_not_called()

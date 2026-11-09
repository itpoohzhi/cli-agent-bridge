import pytest
from unittest.mock import ANY, Mock, call

from tools import system_proxy_zombie_guard as guard


@pytest.fixture
def host():
    system = Mock(spec=guard.System)
    system.lock = Mock()
    system.lock.acquire.return_value = True
    system.monotonic = lambda: 0.0
    system.wall_time = lambda: 1000.0
    values = {}
    system.getenv.side_effect = lambda name, budget: values.get(name)
    system.listener_count.return_value = 0
    system.probe.return_value = False
    system.launch_pids.return_value = set()
    system.processes.return_value = []
    return system, values


def run(host, mode="report"):
    system, _ = host
    return guard.Guard(guard.Config(mode=mode), system).run()


@pytest.mark.parametrize("name", guard.PROXY_NAMES)
@pytest.mark.parametrize("port", sorted(guard.OWNED_PORTS))
def test_report_never_unsets_dead_proxy(host, name, port):
    system, values = host
    values[name] = "http://localhost:%d" % port

    result = run(host)

    assert result.status == "REPORT"
    assert result.exit_code == 0
    assert result.events == [{
        "kind": "environment", "name": name, "port": port,
        "action": "WOULD_UNSET",
    }]
    # One initial observation followed by three retries.
    assert system.probe.call_args_list == [call(port, ANY)] * 4
    assert system.pause.call_args_list == [
        call(0.1, ANY), call(0.2, ANY), call(0.4, ANY),
    ]
    system.unsetenv.assert_not_called()
    system.terminate.assert_not_called()


@pytest.mark.parametrize("name", guard.PROXY_NAMES)
def test_enforce_requires_initial_failure_three_retries_and_final_check(
    host, name
):
    system, values = host
    values[name] = "socks5://127.0.0.1:10820"
    operations = []

    def getenv(variable, budget):
        if variable == name:
            operations.append(("getenv", variable))
        return values.get(variable)

    system.getenv.side_effect = getenv
    system.pause.side_effect = lambda delay, budget: operations.append(
        ("sleep", delay)
    )
    system.listener_count.side_effect = lambda port, budget: (
        operations.append(("listeners", port)) or 0
    )
    system.probe.side_effect = lambda port, budget: (
        operations.append(("probe", port)) or False
    )
    system.unsetenv.side_effect = lambda variable, budget: operations.append(
        ("unset", variable)
    )

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events[0]["action"] == "UNSET"
    assert operations == [
        ("getenv", name),
        ("listeners", 10820), ("probe", 10820),
        ("sleep", 0.1), ("listeners", 10820), ("probe", 10820),
        ("sleep", 0.2), ("listeners", 10820), ("probe", 10820),
        ("sleep", 0.4), ("listeners", 10820), ("probe", 10820),
        ("getenv", name),
        ("listeners", 10820), ("probe", 10820),
        ("getenv", name), ("unset", name),
    ]
    system.unsetenv.assert_called_once_with(name, ANY)


@pytest.mark.parametrize("value", [
    None,
    "",
    "http://proxy.example:44445",
    "http://127.0.0.1:8080",
    "http://localhost:10821",
    "http://localhost:10822",
    "http://user:secret@localhost:44445",
    "http://localhost.evil.example:44445",
    "http://[::2]:44445",
    "http://[::1]:10821",
])
def test_unowned_values_are_never_probed_or_changed(host, value):
    system, values = host
    values["HTTP_PROXY"] = value

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events == []
    system.listener_count.assert_not_called()
    system.probe.assert_not_called()
    system.unsetenv.assert_not_called()


@pytest.mark.parametrize("value", [
    "[::1]:44445",
    "http://[::1]:44445",
    "socks5://[::1]:44445",
])
@pytest.mark.parametrize("mode,action,probe_count", [
    ("report", "WOULD_UNSET", 4),
    ("enforce", "UNSET", 5),
])
def test_ipv6_loopback_proxy_is_probed_as_owned(
    host, value, mode, action, probe_count
):
    system, values = host
    values["HTTP_PROXY"] = value

    result = run(host, mode)

    assert result.exit_code == 0
    assert result.events == [{
        "kind": "environment", "name": "HTTP_PROXY", "port": 44445,
        "action": action,
    }]
    assert system.probe.call_args_list == [
        call(44445, ANY, host="::1")
    ] * probe_count
    assert system.listener_count.call_args_list == [
        call(44445, ANY)
    ] * probe_count
    assert system.pause.call_args_list == [
        call(0.1, ANY), call(0.2, ANY), call(0.4, ANY),
    ]
    if mode == "enforce":
        system.unsetenv.assert_called_once_with("HTTP_PROXY", ANY)
    else:
        system.unsetenv.assert_not_called()
    system.terminate.assert_not_called()


def test_only_allowlisted_names_are_queried_including_lowercase(host):
    system, values = host
    values.update(
        http_proxy="http://localhost:44445",
        NO_PROXY="http://localhost:44445",
        FTP_PROXY="http://localhost:44445",
    )
    system.listener_count.return_value = 1

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert system.getenv.call_args_list == [
        call(name, ANY) for name in guard.PROXY_NAMES
    ]
    assert result.events == [{
        "kind": "environment", "name": "http_proxy", "port": 44445,
        "action": "KEPT", "reason": "endpoint_not_dead",
    }]
    system.probe.assert_not_called()
    system.unsetenv.assert_not_called()


def test_environment_cannot_expand_proxy_scope(host):
    system, values = host
    values["CUSTOM_PROXY"] = "http://localhost:55555"
    config = guard.Config.from_environment({
        "SYSTEM_GUARD_MODE": "enforce",
        "SYSTEM_GUARD_PROXY_NAMES": "CUSTOM_PROXY",
        "SYSTEM_GUARD_OWNED_PORTS": "55555",
    })

    result = guard.Guard(config, system).run()

    assert config.proxy_names == guard.PROXY_NAMES
    assert config.owned_ports == guard.OWNED_PORTS
    assert result.exit_code == 0
    assert result.events == []
    assert system.getenv.call_args_list == [
        call(name, ANY) for name in guard.PROXY_NAMES
    ]
    system.listener_count.assert_not_called()
    system.probe.assert_not_called()
    system.unsetenv.assert_not_called()


def test_any_listener_blocks_cleanup_even_when_tcp_would_fail(host):
    system, values = host
    values["HTTP_PROXY"] = "http://localhost:44445"
    system.listener_count.return_value = 1

    result = run(host, "enforce")

    assert result.events[0]["action"] == "KEPT"
    system.probe.assert_not_called()
    system.unsetenv.assert_not_called()


@pytest.mark.parametrize("recovery_attempt", [0, 1, 2, 3])
def test_tcp_recovery_during_retries_blocks_cleanup(host, recovery_attempt):
    system, values = host
    values["HTTP_PROXY"] = "http://localhost:44445"
    system.probe.side_effect = [False] * recovery_attempt + [True]

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events[0]["action"] == "KEPT"
    assert result.events[0]["reason"] == "endpoint_not_dead"
    assert system.probe.call_count == recovery_attempt + 1
    assert system.pause.call_count == recovery_attempt
    system.unsetenv.assert_not_called()


def test_value_changed_after_retries_is_preserved(host):
    system, values = host
    values["HTTPS_PROXY"] = "http://localhost:44445"
    probes = []

    def probe(port, budget):
        probes.append(port)
        if len(probes) == 4:
            values["HTTPS_PROXY"] = "http://user-proxy.example:9000"
        return False

    system.probe.side_effect = probe

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events[0]["reason"] == "value_changed"
    assert system.probe.call_count == 4
    system.unsetenv.assert_not_called()


@pytest.mark.parametrize("replacement", [
    None,
    "",
    "http://user-proxy.example:9000",
    "http://localhost:10820",
    "http://127.0.0.1:44445",
])
def test_value_changed_during_final_probe_is_preserved(host, replacement):
    system, values = host
    values["HTTPS_PROXY"] = "http://localhost:44445"

    def probe(port, budget):
        if system.probe.call_count == 5:
            values["HTTPS_PROXY"] = replacement
        return False

    system.probe.side_effect = probe

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events == [{
        "kind": "environment", "name": "HTTPS_PROXY", "port": 44445,
        "action": "KEPT", "reason": "value_changed",
    }]
    assert system.probe.call_count == 5
    assert system.getenv.call_args_list.count(call("HTTPS_PROXY", ANY)) == 3
    system.unsetenv.assert_not_called()


@pytest.mark.parametrize("failure", [
    guard.GuardError("query failed"),
    OSError("query unavailable"),
    ValueError("invalid observation"),
])
def test_final_value_query_failure_never_authorizes_unset(host, failure):
    system, values = host
    values["HTTP_PROXY"] = "http://localhost:44445"
    reads = []

    def getenv(name, budget):
        if name == "HTTP_PROXY":
            reads.append(name)
            if len(reads) == 3:
                raise failure
        return values.get(name)

    system.getenv.side_effect = getenv

    result = run(host, "enforce")

    assert result.status == "ERROR"
    assert result.errors == ["ENV_AUDIT_FAILED:HTTP_PROXY"]
    assert system.probe.call_count == 5
    system.unsetenv.assert_not_called()


def test_final_value_query_budget_expiry_never_authorizes_unset(host):
    system, values = host
    values["HTTP_PROXY"] = "http://localhost:44445"
    reads = []

    def getenv(name, budget):
        if name == "HTTP_PROXY":
            reads.append(name)
            if len(reads) == 3:
                raise guard.BudgetExpired("deadline")
        return values.get(name)

    system.getenv.side_effect = getenv

    result = run(host, "enforce")

    assert result.status == "TIMEOUT"
    assert result.errors == ["EXECUTION_BUDGET_EXHAUSTED"]
    system.unsetenv.assert_not_called()
    system.lock.release.assert_called_once_with()


def test_listener_appearing_during_final_recheck_is_preserved(host):
    system, values = host
    values["ALL_PROXY"] = "socks5://localhost:10816"
    system.listener_count.side_effect = [0, 0, 0, 0, 1]

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events[0]["reason"] == "endpoint_recovered"
    assert system.listener_count.call_count == 5
    assert system.probe.call_count == 4
    system.unsetenv.assert_not_called()


def test_tcp_recovery_during_final_recheck_is_preserved(host):
    system, values = host
    values["ALL_PROXY"] = "socks5://localhost:10817"
    system.probe.side_effect = [False, False, False, False, True]

    result = run(host, "enforce")

    assert result.exit_code == 0
    assert result.events[0]["reason"] == "endpoint_recovered"
    assert system.probe.call_count == 5
    system.unsetenv.assert_not_called()


@pytest.mark.parametrize("observation", ["listener_count", "probe"])
def test_unknown_observation_fails_closed(host, observation):
    system, values = host
    values["HTTP_PROXY"] = "http://localhost:44445"
    getattr(system, observation).return_value = None

    result = run(host, "enforce")

    assert result.status == "ERROR"
    assert result.errors == ["ENV_AUDIT_FAILED:HTTP_PROXY"]
    system.unsetenv.assert_not_called()


def test_one_failed_variable_does_not_authorize_or_block_another(host):
    system, values = host
    values["HTTPS_PROXY"] = "http://localhost:44445"

    def getenv(name, budget):
        if name == "HTTP_PROXY":
            raise guard.GuardError("query failed")
        return values.get(name)

    system.getenv.side_effect = getenv

    result = run(host, "enforce")

    assert result.status == "ERROR"
    system.unsetenv.assert_called_once_with("HTTPS_PROXY", ANY)


def test_output_does_not_leak_proxy_credentials(host):
    _, values = host
    values["HTTP_PROXY"] = "http://alice:top-secret@localhost:44445"

    result = run(host, "enforce")

    serialized = guard.json.dumps(result.to_dict())
    assert "top-secret" not in serialized
    assert "alice" not in serialized
    assert result.events == []


def test_unset_failure_is_reported_and_lock_is_released(host):
    system, values = host
    values["HTTP_PROXY"] = "http://localhost:44445"
    system.unsetenv.side_effect = guard.GuardError("failed")

    result = run(host, "enforce")

    assert result.exit_code == 1
    assert result.errors == ["ENV_AUDIT_FAILED:HTTP_PROXY"]
    system.lock.release.assert_called_once_with()

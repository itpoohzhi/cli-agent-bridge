from dataclasses import replace
from unittest.mock import ANY, Mock, call

import pytest

from tools import system_proxy_zombie_guard as guard


@pytest.fixture
def host():
    process = guard.Process(
        pid=8123,
        ppid=1,
        tty=None,
        start_time="Tue Jan 2 03:04:05 2024",
        started_at=0.0,
        command="/opt/bin/droid",
    )
    system = Mock(spec=guard.System)
    system.lock = Mock()
    system.lock.acquire.return_value = True
    system.monotonic = lambda: 0.0
    system.wall_time = lambda: 1000.0
    system.getenv.return_value = None
    system.launch_pids.return_value = set()
    system.processes.return_value = [process]
    system.process.return_value = process
    system.process_listening.return_value = False
    system.arguments.return_value = ()
    return system, process


def run(host, mode="enforce"):
    return guard.Guard(guard.Config(mode=mode), host[0]).run()


def test_report_lists_candidate_without_terminating(host):
    system, process = host

    result = run(host, "report")

    assert result.status == "REPORT"
    assert result.events == [{
        "kind": "process", "pid": process.pid, "action": "WOULD_TERMINATE",
    }]
    system.process_listening.assert_called_once_with(process.pid, ANY)
    system.terminate.assert_not_called()
    system.process.assert_not_called()


def test_enforce_rechecks_listeners_and_final_identity_then_terminates(host):
    system, process = host
    operations = Mock()
    operations.attach_mock(system.process, "process")
    operations.attach_mock(system.process_listening, "process_listening")
    operations.attach_mock(system.terminate, "terminate")

    result = run(host)

    assert result.exit_code == 0
    assert result.events == [{
        "kind": "process", "pid": process.pid, "action": "TERMINATED",
    }]
    assert system.process.call_count == 3
    assert system.process_listening.call_args_list == [
        call(process.pid, ANY),
        call(process.pid, ANY),
    ]
    assert system.launch_pids.call_count == 2
    assert operations.mock_calls == [
        call.process(process.pid, ANY),
        call.process_listening(process.pid, ANY),
        call.process(process.pid, ANY),
        call.process_listening(process.pid, ANY),
        call.process(process.pid, ANY),
        call.terminate(process.pid, ANY),
    ]
    system.terminate.assert_called_once_with(process.pid, ANY)


@pytest.mark.parametrize("changes", [
    {"pid": 1},
    {"ppid": 2},
    {"ppid": 0},
    {"tty": "ttys001"},
    {"tty": ""},
    {"command": "/usr/bin/curl"},
    {"command": "/opt/bin/not-droid"},
    {"command": "/opt/bin/droid-backup"},
    {"command": "/opt/bin/proxyrack-forward.py.old"},
    {"start_time": ""},
    {"started_at": 700.0},
    {"started_at": 701.0},
    {"started_at": 1200.0},
])
def test_non_candidates_are_never_terminated(host, changes):
    system, process = host
    system.processes.return_value = [replace(process, **changes)]

    result = run(host)

    assert result.exit_code == 0
    assert result.events == []
    system.process_listening.assert_not_called()
    system.terminate.assert_not_called()


@pytest.mark.parametrize("tty", [None, "??"])
def test_only_documented_no_tty_representations_are_allowed(host, tty):
    system, process = host
    candidate = replace(process, tty=tty)
    system.processes.return_value = [candidate]
    system.process.return_value = candidate

    result = run(host)

    assert result.events[0]["action"] == "TERMINATED"


def test_age_strictly_greater_than_threshold_is_required(host):
    system, process = host
    candidate = replace(process, started_at=699.0)
    system.processes.return_value = [candidate]
    system.process.return_value = candidate

    assert run(host).events[0]["action"] == "TERMINATED"


def test_launch_agent_is_never_terminated(host):
    system, process = host
    system.launch_pids.return_value = {process.pid}

    result = run(host)

    assert result.events == []
    system.terminate.assert_not_called()


def test_process_becoming_launch_agent_is_preserved(host):
    system, process = host
    system.launch_pids.side_effect = [set(), {process.pid}]

    result = run(host)

    assert result.events[0]["reason"] == "process_changed"
    system.terminate.assert_not_called()


@pytest.mark.parametrize("replacement", [
    None,
    {"start_time": "Wed Jan 3 03:04:05 2024", "started_at": 1.0},
    {"pid": 8124},
    {"ppid": 99},
    {"tty": "ttys002"},
    {"command": "/usr/bin/ssh"},
])
def test_pid_reuse_exit_and_changed_eligibility_are_preserved(host, replacement):
    system, process = host
    system.process.return_value = (
        None if replacement is None else replace(process, **replacement)
    )

    result = run(host)

    assert result.events[0]["action"] == "KEPT"
    system.terminate.assert_not_called()


@pytest.mark.parametrize("unchanged_lookups", [1, 2])
@pytest.mark.parametrize("replacement", [
    None,
    {"start_time": "new-start", "started_at": 10.0},
    {"pid": 8124},
])
def test_pid_reuse_or_exit_during_rechecks_is_preserved(
    host, unchanged_lookups, replacement,
):
    system, process = host
    changed = None if replacement is None else replace(process, **replacement)
    system.process.side_effect = [process] * unchanged_lookups + [changed]

    result = run(host)

    assert result.exit_code == 0
    assert result.events[0]["reason"] == "process_changed"
    assert system.process.call_count == unchanged_lookups + 1
    assert system.process_listening.call_count == unchanged_lookups
    system.terminate.assert_not_called()


@pytest.mark.parametrize("mode", ["report", "enforce"])
@pytest.mark.parametrize("listening,reason", [
    (True, "listening"),
    (None, "listener_unknown"),
])
def test_initial_listener_observation_blocks_termination(
    host, mode, listening, reason,
):
    system, process = host
    system.process_listening.return_value = listening

    result = run(host, mode)

    assert result.exit_code == 0
    assert result.events == [{
        "kind": "process", "pid": process.pid,
        "action": "KEPT", "reason": reason,
    }]
    system.process_listening.assert_called_once_with(process.pid, ANY)
    system.terminate.assert_not_called()


@pytest.mark.parametrize("listening,reason", [
    (True, "listening_at_termination"),
    (None, "listener_unknown"),
])
def test_final_listener_observation_blocks_termination(host, listening, reason):
    system, process = host
    system.process_listening.side_effect = [False, listening]

    result = run(host)

    assert result.exit_code == 0
    assert result.events == [{
        "kind": "process", "pid": process.pid,
        "action": "KEPT", "reason": reason,
    }]
    assert system.process_listening.call_count == 2
    assert system.process.call_count == 2
    system.terminate.assert_not_called()


@pytest.mark.parametrize("arguments", [
    ("/usr/bin/python3", "/opt/proxyrack-forward.py"),
    ("/usr/bin/python", "/opt/proxyrack-forward.py"),
])
def test_explicit_python_script_is_allowed(host, arguments):
    system, process = host
    candidate = replace(process, command="/usr/bin/python3")
    system.processes.return_value = [candidate]
    system.process.return_value = candidate
    system.arguments.return_value = arguments

    result = run(host)

    assert result.events[0]["action"] == "TERMINATED"
    assert system.arguments.call_count == 2


@pytest.mark.parametrize("command,arguments", [
    ("/usr/bin/python3", ("/usr/bin/python3", "-c", "proxyrack-forward.py")),
    ("/usr/bin/python3", ("/usr/bin/python3", "-m", "proxyrack-forward.py")),
    ("/usr/bin/python3", ("/usr/bin/python3", "--",
                         "/opt/proxyrack-forward.py", "--listen")),
    ("/usr/bin/python3", ("/usr/bin/python3", "/opt/unrelated.py",
                         "/opt/proxyrack-forward.py")),
    ("/usr/bin/python3", ("/usr/bin/python3", "/opt/droid")),
    ("/usr/bin/python3", ("/usr/bin/python2", "/opt/proxyrack-forward.py")),
    ("/bin/sh", ("/bin/sh", "/opt/proxyrack-forward.py")),
    ("/usr/bin/node", ("/usr/bin/node", "/opt/droid")),
])
def test_allowlist_is_not_a_command_line_substring_match(
    host, command, arguments
):
    system, process = host
    system.processes.return_value = [replace(process, command=command)]
    system.arguments.return_value = arguments

    result = run(host)

    assert result.events == []
    system.terminate.assert_not_called()


def test_direct_script_executable_is_allowed(host):
    system, process = host
    candidate = replace(process, command="/opt/proxyrack-forward.py")
    system.processes.return_value = [candidate]
    system.process.return_value = candidate

    assert run(host).events[0]["action"] == "TERMINATED"


def test_script_changed_between_snapshot_and_revalidation_is_preserved(host):
    system, process = host
    candidate = replace(process, command="/usr/bin/python3")
    system.processes.return_value = [candidate]
    system.process.return_value = candidate
    system.arguments.side_effect = [
        ("/usr/bin/python3", "/opt/proxyrack-forward.py"),
        ("/usr/bin/python3", "/opt/user-job.py"),
    ]

    result = run(host)

    assert result.events[0]["action"] == "KEPT"
    system.terminate.assert_not_called()


def test_launchctl_failure_prevents_all_process_actions(host):
    system, _ = host
    system.launch_pids.side_effect = guard.GuardError("unavailable")

    result = run(host)

    assert result.status == "ERROR"
    assert result.errors == ["PROCESS_DISCOVERY_FAILED"]
    system.processes.assert_not_called()
    system.terminate.assert_not_called()


def test_launchctl_revalidation_failure_prevents_signal(host):
    system, process = host
    system.launch_pids.side_effect = [set(), guard.GuardError("unavailable")]

    result = run(host)

    assert result.errors == ["PROCESS_AUDIT_FAILED:%d" % process.pid]
    system.terminate.assert_not_called()


def test_signal_permission_failure_is_reported_without_escalation(host):
    system, process = host
    system.terminate.side_effect = PermissionError("denied")

    result = run(host)

    assert result.exit_code == 1
    assert result.errors == ["PROCESS_AUDIT_FAILED:%d" % process.pid]
    system.terminate.assert_called_once_with(process.pid, ANY)
    system.lock.release.assert_called_once_with()


def test_backend_sends_sigterm_only():
    killer = Mock()
    system = guard.System(guard.Config(), killer=killer, lock=Mock())
    budget = guard.Budget(24, lambda: 0)

    system.terminate(8123, budget)

    killer.assert_called_once_with(8123, guard.signal.SIGTERM)

"""Adapter acceptance tests; system mutations are confined to a sandbox."""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools import system_proxy_zombie_guard as guard


PROTECTED_ENVIRONMENT = {
    "SYSTEM_GUARD_RUN_TIMEOUT_LIMIT_S": "100",
    "SYSTEM_GUARD_ORPHAN_AGE_FLOOR_S": "0",
    "SYSTEM_GUARD_PROXY_NAMES": "CUSTOM_PROXY",
    "SYSTEM_GUARD_OWNED_PORTS": "55555",
    "SYSTEM_GUARD_ALLOWED_COMMANDS": "worker",
    "SYSTEM_GUARD_PYTHON_PATTERN": "PythonX",
    "SYSTEM_GUARD_SCRIPT_NAME": "custom.py",
    "SYSTEM_GUARD_PS": "/custom/ps",
    "SYSTEM_GUARD_LSOF": "/custom/lsof",
    "SYSTEM_GUARD_LAUNCHCTL": "/custom/launchctl",
    "SYSTEM_GUARD_OSASCRIPT": "/custom/osascript",
    "SYSTEM_GUARD_NOTIFICATION_TITLE": 'Custom "Guard"\n',
}


@pytest.fixture(autouse=True)
def isolated_lock_locations(monkeypatch, tmp_path_factory):
    root = tmp_path_factory.mktemp("guard-acceptance")
    temporary = root / "tmp"
    temporary.mkdir(mode=0o700)
    home = root / "home"
    home.mkdir(mode=0o700)
    monkeypatch.setattr(guard.tempfile, "tempdir", str(temporary))
    monkeypatch.setenv("HOME", str(home))


def row(pid=8123, command="/opt/bin/droid", ppid=1, tty="??"):
    return f"{pid} {ppid} {tty} Tue Jan 2 03:04:05 2024 {command}\n"


class Sandbox:
    def __init__(self):
        self.values = {
            "HTTP_PROXY": "http://localhost:44445",
            "HTTPS_PROXY": "http://127.0.0.1:10817",
            "ALL_PROXY": "socks5://user-proxy.example:10820",
        }
        self.rows = {8123: row()}
        self.argv = {}
        self.managed = set()
        self.listener_ports = set()
        self.connected_ports = set()
        self.listening_pids = set()
        self.listener_failures = {}
        self.noise = ""
        self.ps_failure = None
        self.fail_launch_list = False
        self.after_listener = None
        self.notifications = []
        self.notification_states = []
        self.notification_error = None
        self.operations = []
        self.now = 0.0
        self.lock = Mock()
        self.lock.acquire.return_value = True
        self.runner = Mock(side_effect=self.command)
        self.spawner = Mock(side_effect=self.spawn)
        self.connector = Mock(side_effect=self.connect)
        self.killer = Mock(side_effect=self.kill)
        self.sleeper = Mock()
        self.started_at = time.mktime((2024, 1, 2, 3, 4, 5, 0, 0, -1))

    @property
    def process_live(self):
        return 8123 in self.rows

    @staticmethod
    def completed(arguments, code=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(arguments, code, stdout, stderr)

    def command(self, arguments, **options):
        assert 0 < options["timeout"] <= 24
        assert options.get("shell", False) is False
        assert options["encoding"] == "utf-8"
        assert options["errors"] == "surrogateescape"
        self.operations.append(tuple(arguments))
        executable = arguments[0]

        if executable == guard.LAUNCHCTL:
            operation = arguments[1]
            if operation == "getenv":
                return self.completed(
                    arguments, stdout=self.values.get(arguments[2], "") + "\n",
                )
            if operation == "unsetenv":
                self.values.pop(arguments[2], None)
                return self.completed(arguments)
            if operation == "list":
                if self.fail_launch_list:
                    return self.completed(arguments, 1, stderr="unavailable")
                text = "PID\tStatus\tLabel\n"
                text += "".join(
                    f"{pid}\t0\tlocal.managed.{pid}\n"
                    for pid in sorted(self.managed)
                )
                return self.completed(arguments, stdout=text)

        if executable == guard.LSOF:
            if "-p" in arguments:
                pid = int(arguments[arguments.index("-p") + 1])
                assert "-iTCP" in arguments
                assert "-sTCP:LISTEN" in arguments
                failure = self.listener_failures.get(pid)
                if isinstance(failure, BaseException):
                    raise failure
                if failure is not None:
                    return self.completed(arguments, *failure)
                listening = pid in self.listening_pids
                if self.after_listener is not None:
                    self.after_listener(pid)
                return self.completed(
                    arguments, 0 if listening else 1,
                    f"p{pid}\n" if listening else "",
                )
            selector = next(a for a in arguments if a.startswith("-iTCP:"))
            port = int(selector.split(":")[1])
            if port in self.listener_ports:
                return self.completed(arguments, stdout="p9000\n")
            return self.completed(arguments, 1)

        if executable == guard.PS:
            if arguments == [guard.PS, "-axo", guard.PROCESS_FORMAT]:
                if isinstance(self.ps_failure, BaseException):
                    raise self.ps_failure
                if self.ps_failure is not None:
                    return self.completed(arguments, self.ps_failure)
                return self.completed(
                    arguments, stdout=self.noise + "".join(self.rows.values()),
                )
            pid = int(arguments[2])
            if arguments[-1] == "args=":
                return self.completed(
                    arguments, stdout=self.argv.get(pid, "/opt/bin/droid") + "\n",
                )
            if arguments[-1] == guard.PROCESS_FORMAT:
                return self.completed(
                    arguments, 0 if pid in self.rows else 1,
                    self.rows.get(pid, ""),
                )
        raise AssertionError(f"unexpected command: {arguments!r}")

    def spawn(self, arguments, **options):
        assert arguments[:2] == [guard.OSASCRIPT, "-e"]
        assert arguments[2].startswith("display notification ")
        assert 'with title "System Proxy Zombie Guard"' in arguments[2]
        assert options == {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "start_new_session": True,
            "close_fds": True,
        }
        self.operations.append(("notify",))
        self.notifications.append(arguments[2])
        self.notification_states.append((dict(self.values), self.process_live))
        if self.notification_error is not None:
            raise self.notification_error
        return Mock(wait=Mock(return_value=0))

    def connect(self, host, port, timeout):
        assert host in ("127.0.0.1", "::1")
        assert port in guard.OWNED_PORTS
        assert timeout > 0
        return port in self.connected_ports

    def kill(self, pid, sig):
        assert sig == signal.SIGTERM
        self.operations.append(("terminate", pid))
        self.rows.pop(pid, None)

    def system(self, config):
        return guard.System(
            config, runner=self.runner, connector=self.connector,
            killer=self.killer, sleeper=self.sleeper,
            monotonic=lambda: self.now,
            wall_time=lambda: self.started_at + 1000,
            lock=self.lock, spawner=self.spawner,
        )


@pytest.fixture
def sandbox():
    return Sandbox()


def test_default_report_is_read_only(sandbox):
    original = dict(sandbox.values)
    config = guard.parse_config([], {})
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "REPORT"
    assert result.exit_code == 0
    assert result.errors == []
    assert sandbox.values == original
    assert sandbox.process_live
    assert [e["action"] for e in result.events] == [
        "WOULD_UNSET", "WOULD_UNSET", "WOULD_TERMINATE",
    ]
    sandbox.killer.assert_not_called()
    assert not any(
        args[:2] == (guard.LAUNCHCTL, "unsetenv")
        for args in sandbox.operations
    )
    sandbox.lock.release.assert_called_once_with()
    assert len(sandbox.notifications) == 1
    assert "WOULD_UNSET: 2" in sandbox.notifications[0]
    assert "WOULD_TERMINATE: 1" in sandbox.notifications[0]


@pytest.mark.parametrize("argv,environ", [
    (["--mode=enforce"], {}),
    ([], {"SYSTEM_GUARD_MODE": "enforce"}),
])
def test_enforce_cleans_only_owned_dead_state(sandbox, argv, environ):
    config = guard.parse_config(argv, environ)
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.exit_code == 0
    assert result.errors == []
    assert sandbox.values == {"ALL_PROXY": "socks5://user-proxy.example:10820"}
    assert not sandbox.process_live
    assert [e["action"] for e in result.events] == [
        "UNSET", "UNSET", "TERMINATED",
    ]
    sandbox.killer.assert_called_once_with(8123, signal.SIGTERM)
    assert sandbox.connector.call_count == 10
    assert [call.args[0] for call in sandbox.sleeper.call_args_list] == [
        0.1, 0.2, 0.4, 0.1, 0.2, 0.4,
    ]
    for index, operation in enumerate(sandbox.operations):
        if operation[:2] == (guard.LAUNCHCTL, "unsetenv"):
            assert sandbox.operations[index - 1] == (
                guard.LAUNCHCTL, "getenv", operation[2],
            )
    assert len(sandbox.notifications) == 1
    assert sandbox.notification_states == [(dict(sandbox.values), False)]
    assert sandbox.operations[-1] == ("notify",)
    assert "user-proxy.example" not in sandbox.notifications[0]
    assert "UNSET: 2" in sandbox.notifications[0]
    assert "TERMINATED: 1" in sandbox.notifications[0]
    assert all(
        call.args[0][0] != guard.OSASCRIPT
        for call in sandbox.runner.call_args_list
    )


@pytest.mark.parametrize("argv,environ", [
    (["--mode=enforce", "--no-notify"], {}),
    (["--mode=enforce", "--no-notify"], {"SYSTEM_GUARD_NOTIFY": "1"}),
    (["--mode=enforce"], {"SYSTEM_GUARD_NOTIFY": "0"}),
    (["--mode=enforce"], {"SYSTEM_GUARD_NOTIFY": "false"}),
])
def test_notifications_can_be_disabled(sandbox, argv, environ):
    config = guard.parse_config(argv, environ)
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert not config.notify
    sandbox.spawner.assert_not_called()
    sandbox.killer.assert_called_once_with(8123, signal.SIGTERM)


@pytest.mark.parametrize("failure", [
    OSError("unavailable"),
    subprocess.TimeoutExpired([guard.OSASCRIPT], 1),
    RuntimeError("adapter failed"),
    guard.BudgetExpired("notifier must not affect cleanup"),
])
def test_notification_errors_do_not_change_cleanup_result(sandbox, failure):
    sandbox.notification_error = failure
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.exit_code == 0
    assert result.errors == []
    assert len(sandbox.notifications) == 1
    assert not sandbox.process_live
    sandbox.lock.release.assert_called_once_with()


def test_notification_spawns_directly_without_waiting_or_threads(
    sandbox, monkeypatch,
):
    config = guard.Config(mode="enforce")
    system = sandbox.system(config)
    caller = threading.current_thread()
    child = Mock()
    child.wait.side_effect = AssertionError("must not wait for notification")
    child.communicate.side_effect = AssertionError("must not communicate")
    thread_factory = Mock(side_effect=AssertionError("must not start a thread"))
    monkeypatch.setattr(threading, "Thread", thread_factory)

    def spawn(arguments, **options):
        assert threading.current_thread() is caller
        sandbox.spawn(arguments, **options)
        assert not sandbox.process_live
        assert "HTTP_PROXY" not in sandbox.values
        assert "HTTPS_PROXY" not in sandbox.values
        sandbox.lock.release.assert_called_once_with()
        sandbox.now = 100000
        return child

    system._spawn = spawn
    result = guard.Guard(config, system).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert len(sandbox.notifications) == 1
    child.wait.assert_not_called()
    child.communicate.assert_not_called()
    thread_factory.assert_not_called()


def test_real_notification_child_is_detached_without_waiting_in_notify():
    config = guard.Config()
    children = []
    waits = []

    def spawn(arguments, **options):
        assert arguments[0] == guard.OSASCRIPT
        assert options["start_new_session"] is True
        child = subprocess.Popen([sys.executable, "-c", "pass"], **options)
        children.append(child)
        original_wait = child.wait
        child.wait = Mock(wraps=original_wait)
        waits.append(child.wait)
        return child

    system = guard.System(config, spawner=spawn)
    try:
        system.notify("test")
        assert len(children) == 1
        waits[0].assert_not_called()
        assert children[0].wait(timeout=5) == 0
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


def test_notification_literal_cannot_be_broken_by_title_or_message():
    title = 'Guard "\\\r\nend'
    message = 'Text "\\\r\nend'
    spawner = Mock(return_value=Mock())
    system = guard.System(
        guard.Config(notification_title=title), spawner=spawner,
    )

    system.notify(message)

    assert spawner.call_count == 1
    script = spawner.call_args.args[0][2]
    assert script == (
        'display notification "Text \\"\\\\  end" '
        'with title "Guard \\"\\\\  end"'
    )
    assert "\r" not in script
    assert "\n" not in script
    assert spawner.call_args.kwargs["start_new_session"] is True
    assert spawner.call_args.kwargs.get("shell", False) is False


def test_cli_report_overrides_enforce_environment(sandbox, capsys):
    original = dict(sandbox.values)
    config = guard.parse_config(
        ["--mode=report"], {"SYSTEM_GUARD_MODE": "enforce"},
    )
    code = guard.main(
        ["--mode=report"], environ={"SYSTEM_GUARD_MODE": "enforce"},
        system=sandbox.system(config),
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "REPORT"
    assert sandbox.values == original
    sandbox.killer.assert_not_called()


def test_live_endpoints_and_managed_process_are_preserved(sandbox):
    sandbox.listener_ports.add(44445)
    sandbox.connected_ports.add(10817)
    sandbox.managed.add(8123)
    original = dict(sandbox.values)
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    assert sandbox.values == original
    assert sandbox.process_live
    assert [e["action"] for e in result.events] == ["KEPT", "KEPT"]
    sandbox.spawner.assert_not_called()
    sandbox.killer.assert_not_called()
    sandbox.sleeper.assert_not_called()


def test_unknown_launchctl_state_never_authorizes_kill(sandbox):
    sandbox.fail_launch_list = True
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ERROR"
    assert result.errors == ["PROCESS_DISCOVERY_FAILED"]
    assert sandbox.process_live
    sandbox.killer.assert_not_called()


def test_second_enforce_run_is_idempotent(sandbox):
    config = guard.Config(mode="enforce")
    system = sandbox.system(config)
    first = guard.Guard(config, system).run()
    second = guard.Guard(config, system).run()

    assert first.exit_code == second.exit_code == 0
    assert second.events == []
    assert len(sandbox.notifications) == 1
    sandbox.killer.assert_called_once_with(8123, signal.SIGTERM)
    assert sandbox.lock.acquire.call_count == sandbox.lock.release.call_count == 2


def test_busy_lock_skips_all_system_activity(sandbox):
    sandbox.lock.acquire.return_value = False
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "SKIPPED_LOCKED"
    assert result.exit_code == 0
    sandbox.runner.assert_not_called()
    sandbox.spawner.assert_not_called()
    sandbox.connector.assert_not_called()
    sandbox.killer.assert_not_called()
    sandbox.lock.release.assert_not_called()


def test_per_user_locks_do_not_conflict_and_release_cleanly(tmp_path):
    paths = []

    def make_lock(uid):
        def opener(path, flags, mode):
            paths.append(path)
            assert flags & os.O_NOFOLLOW
            assert flags & os.O_CLOEXEC
            assert flags & os.O_NONBLOCK
            assert not flags & os.O_TRUNC
            if flags & os.O_CREAT:
                assert flags & os.O_EXCL
            else:
                assert not flags & os.O_EXCL
            assert mode == 0o600
            return os.open(tmp_path / Path(path).name, flags, mode)

        def statter(fd):
            info = os.fstat(fd)
            return SimpleNamespace(
                st_uid=uid, st_mode=info.st_mode, st_nlink=info.st_nlink,
            )

        return guard.FileLock(opener=opener, owner=lambda: uid, statter=statter)

    first = make_lock(501)
    other_user = make_lock(502)
    duplicate = make_lock(501)
    try:
        assert first.acquire()
        assert other_user.acquire()
        assert not duplicate.acquire()
        first.release()
        assert duplicate.acquire()
        assert paths == [
            os.path.join(
                guard._lock_dir(), f"system-proxy-zombie-guard-{uid}.lock",
            )
            for uid in (501, 502, 501, 501, 501, 501)
        ]
        assert all(p.stat().st_mode & 0o777 == 0o600 for p in tmp_path.iterdir())
    finally:
        first.release()
        duplicate.release()
        other_user.release()
    assert len(list(tmp_path.iterdir())) == 2


@pytest.mark.parametrize("permissions", [0o700, 0o755, 0o1777])
def test_same_user_process_skips_contended_temp_lock(
    monkeypatch, tmp_path, permissions,
):
    tmp_path.chmod(permissions)
    monkeypatch.setattr(guard.tempfile, "tempdir", str(tmp_path))
    lock = guard.FileLock()
    path = None
    try:
        assert lock.acquire()
        directory = Path(guard._lock_dir())
        assert directory.stat().st_uid == os.getuid()
        assert directory.stat().st_mode & 0o7777 == 0o700
        if permissions == 0o700:
            assert directory == Path(guard.tempfile.gettempdir())
        else:
            assert directory == Path(
                os.path.expanduser("~/.cache/system-proxy-zombie-guard")
            )
        path = directory / f"system-proxy-zombie-guard-{os.getuid()}.lock"
        assert path.is_file()
        assert path.stat().st_mode & 0o7777 == 0o600
        assert path.stat().st_uid == os.getuid()
        assert path.stat().st_nlink == 1

        # No auditing methods are provided: a lock regression cannot mutate
        # the real environment or terminate a real process.
        script = (
            "from types import SimpleNamespace\n"
            "from tools import system_proxy_zombie_guard as guard\n"
            "system = SimpleNamespace("
            "lock=guard.FileLock(), monotonic=lambda: 0.0)\n"
            "raise SystemExit(guard.main("
            "['--mode=enforce', '--no-notify'], system=system, environ={}))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(guard.__file__).resolve().parent.parent,
            env={
                **os.environ,
                "TMPDIR": str(tmp_path),
                "TEMP": str(tmp_path),
                "TMP": str(tmp_path),
            },
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {
            "mode": "enforce", "status": "SKIPPED_LOCKED",
            "events": [], "errors": [],
        }
    finally:
        lock.release()
    assert path is not None
    assert path.exists()
    try:
        assert lock.acquire()
    finally:
        lock.release()


@pytest.mark.parametrize("kind", [
    "symlink", "foreign", "permissive", "hardlink", "directory",
])
def test_unsafe_lock_is_not_acquired_and_is_not_an_error(
    sandbox, tmp_path, kind,
):
    uid = os.getuid()
    path = tmp_path / f"system-proxy-zombie-guard-{uid}.lock"
    target = tmp_path / "target"
    target.write_text("unchanged")
    if kind == "symlink":
        path.symlink_to(target)
    elif kind == "directory":
        path.mkdir()
    else:
        path.write_text("")
        path.chmod(0o666 if kind == "permissive" else 0o600)
        if kind == "hardlink":
            os.link(path, tmp_path / "second-link")

    def opener(requested, flags, mode):
        assert requested == os.path.join(
            guard._lock_dir(), f"system-proxy-zombie-guard-{uid}.lock",
        )
        return os.open(path, flags, mode)

    def statter(fd):
        info = os.fstat(fd)
        return SimpleNamespace(
            st_uid=uid + 1 if kind == "foreign" else info.st_uid,
            st_mode=info.st_mode, st_nlink=info.st_nlink,
        )

    config = guard.Config(mode="enforce")
    system = sandbox.system(config)
    system.lock = guard.FileLock(opener=opener, statter=statter)
    result = guard.Guard(config, system).run()

    assert result.status == "SKIPPED_LOCKED"
    assert result.exit_code == 0
    assert target.read_text() == "unchanged"
    sandbox.runner.assert_not_called()
    sandbox.killer.assert_not_called()
    sandbox.spawner.assert_not_called()


def test_unsafe_private_lock_directory_prevents_all_auditing(
    sandbox, monkeypatch, tmp_path,
):
    tmp_path.chmod(0o755)
    monkeypatch.setattr(guard.tempfile, "tempdir", str(tmp_path))
    private = Path(os.path.expanduser("~/.cache/system-proxy-zombie-guard"))
    private.mkdir(mode=0o755, parents=True)
    private.chmod(0o755)
    config = guard.Config(mode="enforce")
    system = sandbox.system(config)
    system.lock = guard.FileLock()

    result = guard.Guard(config, system).run()

    assert result.status == "ERROR"
    assert result.errors == ["LOCK_FAILED"]
    sandbox.runner.assert_not_called()
    sandbox.killer.assert_not_called()
    sandbox.spawner.assert_not_called()


@pytest.mark.parametrize("noise", [
    "garbage\n",
    "x 1 ?? Tue Jan 2 03:04:05 2024 /opt/bin/droid\n",
    "9000 nope ?? Tue Jan 2 03:04:05 2024 /opt/bin/droid\n",
    "9000 1 ?? Tue Jan\n",
    "9000 1 ?? Tue Jan 99 03:04:05 2024 /opt/bin/droid\n",
    "9000 1 ?? Tue Jan 2 03:04:05 2024 /opt/\udcff/droid\n",
    "9000 77 ?? not a date at all /opt/bin/python3\n",
    "9000 1 ?? not a date at all /opt/bin/unrelated\n",
])
def test_malformed_and_unrelated_ps_rows_do_not_abort(sandbox, noise, caplog):
    sandbox.noise = noise
    config = guard.Config(mode="enforce")
    with caplog.at_level(logging.DEBUG, logger=guard.__name__):
        result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    sandbox.killer.assert_called_once_with(8123, signal.SIGTERM)
    assert any("ps skipped_rows=1" in r.message for r in caplog.records)


def test_raw_non_utf8_ps_line_is_skipped(caplog):
    text = b"\xff invalid\n" + row().encode()
    with caplog.at_level(logging.DEBUG, logger=guard.__name__):
        processes = guard._parse_processes(text)
    assert [p.pid for p in processes] == [8123]
    assert [r.message for r in caplog.records] == ["ps skipped_rows=1"]


@pytest.mark.parametrize("command,argv,expected", [
    ("/opt/python", ("/opt/python", "/srv/proxyrack-forward.py"), True),
    ("/opt/python3", ("/opt/python3", "/srv/proxyrack-forward.py"), True),
    ("/opt/python3.14", ("python3.14", "/srv/proxyrack-forward.py"), True),
    (
        "/Library/Frameworks/Python.framework/Versions/3.14/Python",
        ("/opt/bin/python3.14", "/srv/proxyrack-forward.py"),
        True,
    ),
    ("/opt/notpython3", ("notpython3", "proxyrack-forward.py"), False),
    ("/opt/python3-helper", ("python3-helper", "proxyrack-forward.py"), False),
    ("/opt/python3.14", ("sh", "proxyrack-forward.py"), False),
    ("/opt/python3.14", ("python3.14", "proxyrack-forward.py.old"), False),
    ("/opt/python3.14", ("python3.14", "-m", "proxyrack-forward.py"), False),
    ("/opt/python3.14", ("python3.14", "--", "proxyrack-forward.py"), False),
    ("/opt/python3.14", ("python3.14", "other.py", "proxyrack-forward.py"), False),
    ("/opt/python3.14", ("python3.14",), False),
    ("/opt/droid-helper", (), False),
    ("/opt/droid", (), True),
])
def test_interpreter_and_script_matching_is_token_exact(command, argv, expected):
    assert guard.allowed_command(command, argv) is expected


@pytest.mark.parametrize("command", [
    "/opt/bin/python3.14",
    "/Library/Frameworks/Python.framework/Versions/3.14/Python",
])
def test_python_orphans_are_found_end_to_end(sandbox, command):
    sandbox.values.clear()
    sandbox.rows[8123] = row(command=command)
    sandbox.argv[8123] = (
        '"/opt/bin/python3.14" "/srv/proxyrack-forward.py" --config "/a b"'
    )
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    sandbox.killer.assert_called_once_with(8123, signal.SIGTERM)


@pytest.mark.parametrize("arguments", [
    '"unterminated',
    "python3.14 /srv/proxyrack-forward.py\\",
    "python3.14",
    "python3.14 /srv/proxyrack-forward.py\udcff",
    "python3.14 other.py --label proxyrack-forward.py",
])
def test_invalid_or_foreign_arguments_are_skipped(sandbox, arguments):
    sandbox.values.clear()
    sandbox.rows[8123] = row(command="/opt/bin/python3.14")
    sandbox.argv[8123] = arguments
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert result.events == []
    sandbox.killer.assert_not_called()


def test_arguments_are_not_requested_for_non_candidates(sandbox):
    sandbox.values.clear()
    sandbox.rows = {
        8123: row(command="/opt/python3.14", ppid=99),
        8124: row(pid=8124, command="/opt/unrelated"),
    }
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    assert not any(
        call.args[0][-1] == "args=" for call in sandbox.runner.call_args_list
    )
    sandbox.killer.assert_not_called()


@pytest.mark.parametrize("failure", [
    2,
    OSError("ps unavailable"),
    subprocess.TimeoutExpired([guard.PS], 1),
])
def test_ps_execution_failure_remains_an_error(sandbox, failure):
    sandbox.values.clear()
    sandbox.ps_failure = failure
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ERROR"
    assert result.errors == ["PROCESS_DISCOVERY_FAILED"]
    sandbox.killer.assert_not_called()


@pytest.mark.parametrize("mode", ["report", "enforce"])
def test_listening_process_is_not_considered_an_orphan(sandbox, mode):
    sandbox.values.clear()
    sandbox.listening_pids.add(8123)
    config = guard.Config(mode=mode)
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    assert result.errors == []
    assert result.events == [{
        "kind": "process", "pid": 8123,
        "action": "KEPT", "reason": "listening",
    }]
    assert sandbox.process_live
    sandbox.killer.assert_not_called()
    sandbox.spawner.assert_not_called()


@pytest.mark.parametrize("failure", [
    (2, "", "denied"),
    (0, "", ""),
    (0, "unexpected output\n", ""),
    (1, "", "warning"),
    OSError("lsof unavailable"),
    subprocess.TimeoutExpired([guard.LSOF], 1),
])
def test_lsof_failure_preserves_process_and_other_candidates_continue(
    sandbox, failure, caplog,
):
    sandbox.values.clear()
    sandbox.rows[8124] = row(pid=8124)
    sandbox.listener_failures[8123] = failure
    config = guard.Config(mode="enforce")
    with caplog.at_level(logging.DEBUG, logger=guard.__name__):
        result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert sandbox.process_live
    sandbox.killer.assert_called_once_with(8124, signal.SIGTERM)
    assert result.events[0]["reason"] == "listener_unknown"
    assert any("pid=8123 skipped: listener_unknown" in r.message
               for r in caplog.records)


@pytest.mark.parametrize("change", ["ppid", "identity", "gone"])
def test_identity_is_rechecked_after_lsof_before_terminate(sandbox, change):
    sandbox.values.clear()

    def change_process(pid):
        if change == "ppid":
            sandbox.rows[pid] = row(ppid=99)
        elif change == "identity":
            sandbox.rows[pid] = row().replace("03:04:05", "03:04:06")
        else:
            sandbox.rows.pop(pid)

    sandbox.after_listener = change_process
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    assert result.events[0]["reason"] == "process_changed"
    sandbox.killer.assert_not_called()


def test_socket_and_identity_are_rechecked_before_terminate(sandbox):
    sandbox.values.clear()
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    index = sandbox.operations.index(("terminate", 8123))
    socket_check = (
        guard.LSOF, "-nP", "-a", "-p", "8123", "-iTCP",
        "-sTCP:LISTEN", "-F", "p",
    )
    identity_check = (
        guard.PS, "-p", "8123", "-o", guard.PROCESS_FORMAT,
    )
    assert sandbox.operations[index - 5:index] == [
        identity_check,
        socket_check,
        identity_check,
        socket_check,
        identity_check,
    ]
    assert sandbox.operations.count(socket_check) == 2
    assert sandbox.operations.count(identity_check) == 3


@pytest.mark.parametrize("change", ["identity", "gone"])
def test_final_identity_lookup_after_second_socket_check_prevents_kill(
    sandbox, change,
):
    sandbox.values.clear()
    observations = []

    def change_process(pid):
        observations.append(pid)
        if len(observations) == 2:
            if change == "identity":
                sandbox.rows[pid] = row().replace("03:04:05", "03:04:06")
            else:
                sandbox.rows.pop(pid)

    sandbox.after_listener = change_process
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert observations == [8123, 8123]
    assert result.events == [{
        "kind": "process", "pid": 8123,
        "action": "KEPT", "reason": "process_changed",
    }]
    sandbox.killer.assert_not_called()
    sandbox.spawner.assert_not_called()


@pytest.mark.parametrize("appearance", ["after_lsof", "during_final_ps"])
def test_process_starting_to_listen_before_termination_is_preserved(
    sandbox, appearance,
):
    sandbox.values.clear()

    if appearance == "after_lsof":
        sandbox.after_listener = sandbox.listening_pids.add
    else:
        original_command = sandbox.runner.side_effect
        lookups = []

        def command(arguments, **options):
            completed = original_command(arguments, **options)
            if arguments == [
                guard.PS, "-p", "8123", "-o", guard.PROCESS_FORMAT,
            ]:
                lookups.append(arguments)
                if len(lookups) == 2:
                    sandbox.listening_pids.add(8123)
            return completed

        sandbox.runner.side_effect = command

    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert result.events == [{
        "kind": "process", "pid": 8123,
        "action": "KEPT", "reason": "listening_at_termination",
    }]
    assert sandbox.process_live
    sandbox.killer.assert_not_called()
    sandbox.spawner.assert_not_called()


@pytest.mark.parametrize("failure", [
    (2, "", "denied"),
    (0, "", ""),
    (0, "unexpected output\n", ""),
    (1, "", "warning"),
    OSError("lsof unavailable"),
    subprocess.TimeoutExpired([guard.LSOF], 1),
])
def test_unknown_final_socket_observation_never_authorizes_termination(
    sandbox, failure,
):
    sandbox.values.clear()

    def fail_next_observation(pid):
        sandbox.listener_failures[pid] = failure

    sandbox.after_listener = fail_next_observation
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert result.events == [{
        "kind": "process", "pid": 8123,
        "action": "KEPT", "reason": "listener_unknown",
    }]
    assert sandbox.process_live
    sandbox.killer.assert_not_called()
    sandbox.spawner.assert_not_called()


def test_lowercase_ipv6_proxy_is_checked_without_initial_sleep(sandbox):
    sandbox.values = {"http_proxy": "http://[::1]:44445"}
    sandbox.rows.clear()
    order = []
    original_connect = sandbox.connector.side_effect
    sandbox.connector.side_effect = lambda *args: (
        order.append("probe"), original_connect(*args)
    )[1]
    sandbox.sleeper.side_effect = lambda delay: order.append("pause")
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    assert sandbox.values == {}
    assert order[0] == "probe"
    assert all(call.args[0] == "::1" for call in sandbox.connector.call_args_list)


@pytest.mark.parametrize("replacement", [
    None,
    "http://user-proxy.example:9000",
    "http://localhost:10820",
])
def test_proxy_value_changed_during_final_tcp_check_is_not_unset(
    sandbox, replacement,
):
    sandbox.values = {"HTTP_PROXY": "http://localhost:44445"}
    sandbox.rows.clear()

    def connect(host, port, timeout):
        if sandbox.connector.call_count == 5:
            if replacement is None:
                sandbox.values.pop("HTTP_PROXY", None)
            else:
                sandbox.values["HTTP_PROXY"] = replacement
        return False

    sandbox.connector.side_effect = connect
    config = guard.Config(mode="enforce")
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.status == "ENFORCED"
    assert result.errors == []
    assert result.events == [{
        "kind": "environment", "name": "HTTP_PROXY", "port": 44445,
        "action": "KEPT", "reason": "value_changed",
    }]
    assert sandbox.values.get("HTTP_PROXY") == replacement
    assert sandbox.connector.call_count == 5
    assert not any(
        operation[:2] == (guard.LAUNCHCTL, "unsetenv")
        for operation in sandbox.operations
    )
    sandbox.spawner.assert_not_called()


def test_operational_settings_are_configurable_but_scope_is_fixed():
    config = guard.parse_config([], {
        **PROTECTED_ENVIRONMENT,
        "SYSTEM_GUARD_TIMEOUT_S": "12",
        "SYSTEM_GUARD_COMMAND_TIMEOUT_S": "2",
        "SYSTEM_GUARD_CONNECT_TIMEOUT_S": "0.5",
        "SYSTEM_GUARD_ORPHAN_MIN_AGE_S": "600",
        "SYSTEM_GUARD_RETRY_BACKOFF_S": "0,0.5",
        "SYSTEM_GUARD_NOTIFY": "false",
    })

    assert config.run_timeout_s == 12
    assert config.command_timeout_s == 2
    assert config.connect_timeout_s == 0.5
    assert config.orphan_min_age_s == 600
    assert config.retry_backoff_s == (0, 0.5)
    assert config.notify is False
    defaults = guard.Config()
    for name in (
        "run_timeout_limit_s", "orphan_age_floor_s", "proxy_names",
        "owned_ports", "allowed_commands", "python_pattern", "script_name",
        "ps", "lsof", "launchctl", "osascript", "notification_title",
    ):
        assert getattr(config, name) == getattr(defaults, name)
    assert guard.parse_endpoint(
        "http://localhost:55555", config.owned_ports,
    ) is None
    assert not guard.allowed_command(
        "/custom/PythonX", ("PythonX", "/srv/custom.py"), config,
    )
    assert guard.allowed_command(
        "/usr/bin/python3", ("python3", "/srv/proxyrack-forward.py"), config,
    )


@pytest.mark.parametrize("environ", [
    {"SYSTEM_GUARD_NOTIFY": "invalid"},
    {"SYSTEM_GUARD_TIMEOUT_S": "nan"},
    {"SYSTEM_GUARD_RUN_TIMEOUT_S": "25"},
    {"SYSTEM_GUARD_COMMAND_TIMEOUT_S": "0"},
    {"SYSTEM_GUARD_ORPHAN_MIN_AGE_S": "299"},
    {"SYSTEM_GUARD_RETRY_BACKOFF_S": "0.4,0.1"},
])
def test_invalid_operational_configuration_is_rejected(environ):
    with pytest.raises(SystemExit):
        guard.parse_config([], environ)


@pytest.mark.parametrize("environ", [
    {"SYSTEM_GUARD_PYTHON_PATTERN": "["},
    {"SYSTEM_GUARD_OWNED_PORTS": "0"},
    {"SYSTEM_GUARD_PROXY_NAMES": "BAD-NAME"},
    {"SYSTEM_GUARD_RUN_TIMEOUT_LIMIT_S": "not-a-number"},
    {"SYSTEM_GUARD_ORPHAN_AGE_FLOOR_S": "nan"},
])
def test_invalid_protected_environment_values_are_ignored(environ):
    assert guard.parse_config([], environ) == guard.Config()


def test_only_scoped_executables_and_launchctl_operations_are_used(sandbox):
    config = guard.parse_config(["--mode=enforce"], PROTECTED_ENVIRONMENT)
    result = guard.Guard(config, sandbox.system(config)).run()

    assert result.exit_code == 0
    assert {call.args[0][0] for call in sandbox.runner.call_args_list} == {
        guard.LAUNCHCTL, guard.PS, guard.LSOF,
    }
    assert {
        call.args[0][1] for call in sandbox.runner.call_args_list
        if call.args[0][0] == guard.LAUNCHCTL
    } == {"getenv", "unsetenv", "list"}
    assert sandbox.spawner.call_count == 1
    sandbox.killer.assert_called_once_with(8123, signal.SIGTERM)


def test_guard_source_stays_within_size_limit():
    assert Path(guard.__file__).stat().st_size <= 32_000

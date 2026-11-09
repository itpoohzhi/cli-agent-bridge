import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock

import pytest

from tools import system_proxy_zombie_guard as guard


@pytest.fixture(autouse=True)
def isolated_lock_locations(monkeypatch, tmp_path_factory):
    root = tmp_path_factory.mktemp("guard-runtime")
    temporary = root / "tmp"
    temporary.mkdir(mode=0o700)
    home = root / "home"
    home.mkdir(mode=0o700)
    monkeypatch.setattr(tempfile, "tempdir", str(temporary))
    monkeypatch.setenv("HOME", str(home))


def make_host():
    system = Mock(spec=guard.System)
    system.lock = Mock()
    system.lock.acquire.return_value = True
    system.monotonic = lambda: 0.0
    system.wall_time = lambda: 1000.0
    system.getenv.return_value = None
    system.launch_pids.return_value = set()
    system.processes.return_value = []
    return system


def fake_lock(**overrides):
    hooks = {
        "opener": Mock(return_value=91),
        "locker": Mock(),
        "closer": Mock(),
        "statter": Mock(return_value=Mock(
            st_mode=0o100600, st_uid=501, st_nlink=1
        )),
        "owner": lambda: 501,
    }
    hooks.update(overrides)
    return guard.FileLock(**hooks), hooks


def test_default_configuration_is_report():
    assert guard.parse_config([], {}).mode == "report"


@pytest.mark.parametrize("argv,environ,expected", [
    (["--mode=enforce"], {}, "enforce"),
    ([], {"SYSTEM_GUARD_MODE": "enforce"}, "enforce"),
    (["--mode=report"], {"SYSTEM_GUARD_MODE": "enforce"}, "report"),
    (["--mode=enforce"], {"SYSTEM_GUARD_MODE": "invalid"}, "enforce"),
])
def test_explicit_mode_and_cli_precedence(argv, environ, expected):
    assert guard.parse_config(argv, environ).mode == expected


def test_operational_settings_are_configurable():
    config = guard.parse_config([], {
        "SYSTEM_GUARD_TIMEOUT_S": "12",
        "SYSTEM_GUARD_COMMAND_TIMEOUT_S": "0.7",
        "SYSTEM_GUARD_CONNECT_TIMEOUT_S": "0.05",
        "SYSTEM_GUARD_ORPHAN_MIN_AGE_S": "600",
        "SYSTEM_GUARD_RETRY_BACKOFF_S": "0.2,0.4,0.8",
        "SYSTEM_GUARD_NOTIFY": "false",
    })

    assert config.run_timeout_s == 12
    assert config.command_timeout_s == 0.7
    assert config.connect_timeout_s == 0.05
    assert config.orphan_min_age_s == 600
    assert config.retry_backoff_s == (0.2, 0.4, 0.8)
    assert config.notify is False


def test_canonical_run_timeout_setting_takes_precedence_over_legacy_alias():
    config = guard.parse_config([], {
        "SYSTEM_GUARD_RUN_TIMEOUT_S": "12",
        "SYSTEM_GUARD_TIMEOUT_S": "18",
    })

    assert config.run_timeout_s == 12


def test_environment_field_allowlist_is_exact():
    assert guard.ALLOWED_ENV_FIELDS == frozenset((
        "mode", "run_timeout_s", "command_timeout_s", "connect_timeout_s",
        "orphan_min_age_s", "retry_backoff_s", "notify",
    ))


@pytest.mark.parametrize("name,value", [
    ("launchctl", "/tmp/launchctl"),
    ("ps", "/tmp/ps"),
    ("lsof", "/tmp/lsof"),
    ("osascript", "/tmp/osascript"),
    ("script_name", "foreign.py"),
    ("python_pattern", "["),
    ("allowed_commands", "foreign"),
    ("owned_ports", "0"),
    ("proxy_names", "BAD-NAME"),
    ("run_timeout_limit_s", "nan"),
    ("orphan_age_floor_s", "-1"),
    ("notification_title", '" & do shell script "unexpected'),
])
def test_protected_settings_are_ignored_from_environment(name, value):
    config = guard.Config.from_environment({
        "SYSTEM_GUARD_" + name.upper(): value,
    })

    assert config == guard.Config()


def test_protected_environment_fields_are_not_even_read():
    class OperationalEnvironment(dict):
        def get(self, key, default=None):
            allowed = {
                "SYSTEM_GUARD_" + name.upper()
                for name in guard.ALLOWED_ENV_FIELDS
            }
            allowed.add("SYSTEM_GUARD_TIMEOUT_S")
            assert key in allowed
            return super().get(key, default)

    config = guard.Config.from_environment(OperationalEnvironment({
        "SYSTEM_GUARD_MODE": "enforce",
        "SYSTEM_GUARD_LAUNCHCTL": "/tmp/launchctl",
    }))

    assert config.mode == "enforce"
    assert config.launchctl == guard.LAUNCHCTL


@pytest.mark.parametrize("settings", [
    {"run_timeout_s": 25},
    {"run_timeout_s": 25, "run_timeout_limit_s": 100},
    {"orphan_min_age_s": 299},
    {"orphan_min_age_s": 299, "orphan_age_floor_s": 0},
    {"launchctl": "/tmp/launchctl"},
    {"ps": "/tmp/ps"},
    {"lsof": "/tmp/lsof"},
    {"osascript": "/tmp/osascript"},
])
def test_direct_configuration_cannot_bypass_safety_invariants(settings):
    with pytest.raises(ValueError):
        guard.Config(**settings)


@pytest.mark.parametrize("environ", [
    {
        "SYSTEM_GUARD_TIMEOUT_S": "25",
        "SYSTEM_GUARD_RUN_TIMEOUT_LIMIT_S": "100",
    },
    {
        "SYSTEM_GUARD_RUN_TIMEOUT_S": "25",
        "SYSTEM_GUARD_RUN_TIMEOUT_LIMIT_S": "100",
    },
    {
        "SYSTEM_GUARD_ORPHAN_MIN_AGE_S": "299",
        "SYSTEM_GUARD_ORPHAN_AGE_FLOOR_S": "0",
    },
])
def test_environment_cannot_weaken_safety_limits(environ):
    with pytest.raises(SystemExit) as caught:
        guard.parse_config([], environ)

    assert caught.value.code == 2


@pytest.mark.parametrize("value,expected", [
    ("0", (0.0,)),
    ("0.1,0.2", (0.1, 0.2)),
    ("0.1,0.1,0.2", (0.1, 0.1, 0.2)),
])
def test_nonempty_nondecreasing_backoff_is_allowed(value, expected):
    config = guard.parse_config([], {"SYSTEM_GUARD_RETRY_BACKOFF_S": value})

    assert config.retry_backoff_s == expected


@pytest.mark.parametrize("key,value", [
    ("SYSTEM_GUARD_MODE", "ENFORCE"),
    ("SYSTEM_GUARD_TIMEOUT_S", "25"),
    ("SYSTEM_GUARD_TIMEOUT_S", "0"),
    ("SYSTEM_GUARD_TIMEOUT_S", "nan"),
    ("SYSTEM_GUARD_RUN_TIMEOUT_S", "25"),
    ("SYSTEM_GUARD_RUN_TIMEOUT_S", "inf"),
    ("SYSTEM_GUARD_COMMAND_TIMEOUT_S", "-1"),
    ("SYSTEM_GUARD_COMMAND_TIMEOUT_S", "inf"),
    ("SYSTEM_GUARD_CONNECT_TIMEOUT_S", "0"),
    ("SYSTEM_GUARD_ORPHAN_MIN_AGE_S", "299"),
    ("SYSTEM_GUARD_ORPHAN_MIN_AGE_S", "nan"),
    ("SYSTEM_GUARD_RETRY_BACKOFF_S", ""),
    ("SYSTEM_GUARD_RETRY_BACKOFF_S", "0.2,0.1,0.4"),
    ("SYSTEM_GUARD_RETRY_BACKOFF_S", "0.1,nan,0.4"),
    ("SYSTEM_GUARD_RETRY_BACKOFF_S", "-1,0.2,0.4"),
    ("SYSTEM_GUARD_TIMEOUT_S", "not-a-number"),
    ("SYSTEM_GUARD_NOTIFY", "invalid"),
])
def test_invalid_configuration_exits_before_any_system_calls(key, value):
    with pytest.raises(SystemExit) as caught:
        guard.parse_config([], {key: value})
    assert caught.value.code == 2


def test_invalid_cli_mode_is_rejected():
    with pytest.raises(SystemExit) as caught:
        guard.parse_config(["--mode=unsafe"], {})
    assert caught.value.code == 2


@pytest.mark.parametrize("permissions", [0o700, 0o755, 0o1777])
def test_default_lock_directory_is_private_and_owned(
    monkeypatch, tmp_path, permissions,
):
    tmp_path.chmod(permissions)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    directory = Path(guard._lock_dir())
    info = directory.lstat()
    expected = (
        Path(tempfile.gettempdir())
        if permissions == 0o700
        else Path(os.path.expanduser("~/.cache/system-proxy-zombie-guard"))
    )

    assert directory == expected
    assert stat.S_ISDIR(info.st_mode)
    assert stat.S_IMODE(info.st_mode) == 0o700
    assert info.st_uid == os.getuid()
    assert os.path.basename(guard.LOCK_PATH) == (
        f"system-proxy-zombie-guard-{os.getuid()}.lock"
    )


def test_lock_uses_runtime_private_temp_directory(monkeypatch, tmp_path):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    lock, hooks = fake_lock()

    try:
        assert lock.acquire() is True
        assert guard._lock_dir() == tempfile.gettempdir()
        assert hooks["opener"].call_args.args[0] == str(
            tmp_path / "system-proxy-zombie-guard-501.lock"
        )
    finally:
        lock.release()


@pytest.mark.parametrize("permissions", [0o755, 0o777, 0o1777])
def test_shared_temp_directory_uses_private_home_cache(
    monkeypatch, tmp_path, permissions,
):
    tmp_path.chmod(permissions)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    expected = Path(os.path.expanduser("~/.cache/system-proxy-zombie-guard"))

    assert guard._lock_dir() == str(expected)
    assert guard._lock_dir() == str(expected)
    info = expected.lstat()
    assert stat.S_ISDIR(info.st_mode)
    assert stat.S_IMODE(info.st_mode) == 0o700
    assert info.st_uid == os.getuid()
    assert stat.S_IMODE(tmp_path.stat().st_mode) == permissions


def test_foreign_temp_directory_uses_owned_private_home_cache(
    monkeypatch, tmp_path,
):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    original_lstat = os.lstat

    def lstat(path, *args, **kwargs):
        info = original_lstat(path, *args, **kwargs)
        if os.fspath(path) == str(tmp_path):
            return SimpleNamespace(
                st_mode=info.st_mode, st_uid=os.getuid() + 1,
            )
        return info

    monkeypatch.setattr(guard.os, "lstat", lstat)
    expected = Path(os.path.expanduser("~/.cache/system-proxy-zombie-guard"))

    assert guard._lock_dir() == str(expected)
    assert expected.stat().st_uid == os.getuid()
    assert stat.S_IMODE(expected.stat().st_mode) == 0o700


@pytest.mark.parametrize("kind", [
    "permissive", "special_mode", "symlink", "file", "foreign",
])
def test_preexisting_unsafe_private_directory_is_rejected(
    monkeypatch, tmp_path, kind,
):
    tmp_path.chmod(0o755)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    private = Path(os.path.expanduser("~/.cache/system-proxy-zombie-guard"))
    private.parent.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "target"
    target.mkdir(mode=0o700)

    if kind == "symlink":
        private.symlink_to(target, target_is_directory=True)
    elif kind == "file":
        private.write_text("unchanged")
    else:
        private.mkdir(mode=0o700)
        if kind == "permissive":
            private.chmod(0o755)
        elif kind == "special_mode":
            private.chmod(0o1700)

    original_lstat = os.lstat

    if kind == "foreign":
        def lstat(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if os.fspath(path) == str(private):
                return SimpleNamespace(
                    st_mode=info.st_mode, st_uid=os.getuid() + 1,
                )
            return info

        monkeypatch.setattr(guard.os, "lstat", lstat)

    with pytest.raises(guard.GuardError):
        guard._lock_dir()

    if kind == "permissive":
        assert stat.S_IMODE(private.stat().st_mode) == 0o755
    if kind == "symlink":
        assert private.is_symlink()
    if kind == "file":
        assert private.read_text() == "unchanged"
    assert stat.S_IMODE(target.stat().st_mode) == 0o700


@pytest.mark.parametrize("uid", [501, 502])
def test_lock_is_per_user_exclusive_nonblocking_and_cloexec(uid):
    lock, hooks = fake_lock(
        owner=lambda: uid,
        statter=Mock(return_value=Mock(
            st_mode=0o100600, st_uid=uid, st_nlink=1
        )),
    )

    assert lock.acquire() is True

    hooks["locker"].assert_called_once_with(
        91, guard.fcntl.LOCK_EX | guard.fcntl.LOCK_NB
    )
    path, flags, permissions = hooks["opener"].call_args.args
    assert path == os.path.join(
        guard._lock_dir(), f"system-proxy-zombie-guard-{uid}.lock",
    )
    assert permissions == 0o600
    assert flags & os.O_CREAT
    assert flags & os.O_EXCL
    assert flags & os.O_NOFOLLOW
    assert flags & os.O_CLOEXEC
    assert flags & os.O_NONBLOCK
    assert not flags & os.O_TRUNC

    lock.release()

    assert hooks["locker"].call_args.args == (91, guard.fcntl.LOCK_UN)
    hooks["closer"].assert_called_once_with(91)


def test_existing_lock_is_reopened_without_creation_or_truncation():
    opener = Mock(side_effect=[FileExistsError(), 91])
    lock, hooks = fake_lock(opener=opener)

    try:
        assert lock.acquire() is True

        create, reopen = opener.call_args_list
        assert create.args[0] == reopen.args[0]
        assert create.args[1] & os.O_CREAT
        assert create.args[1] & os.O_EXCL
        assert not reopen.args[1] & os.O_CREAT
        assert not reopen.args[1] & os.O_EXCL
        assert not reopen.args[1] & os.O_TRUNC
        assert reopen.args[1] & os.O_NOFOLLOW
        assert reopen.args[1] & os.O_CLOEXEC
        assert reopen.args[1] & os.O_NONBLOCK
        assert reopen.args[2] == 0o600
    finally:
        lock.release()

    hooks["closer"].assert_called_once_with(91)


@pytest.mark.parametrize("exception", [BlockingIOError(), PermissionError()])
def test_contended_lock_closes_descriptor_without_waiting(exception):
    lock, hooks = fake_lock(locker=Mock(side_effect=exception))

    assert lock.acquire() is False

    hooks["closer"].assert_called_once_with(91)
    lock.release()
    hooks["closer"].assert_called_once_with(91)


@pytest.mark.parametrize("fields", [
    {"st_mode": 0o010600, "st_uid": 501, "st_nlink": 1},
    {"st_mode": 0o100644, "st_uid": 501, "st_nlink": 1},
    {"st_mode": 0o104600, "st_uid": 501, "st_nlink": 1},
    {"st_mode": 0o100600, "st_uid": 502, "st_nlink": 1},
    {"st_mode": 0o100600, "st_uid": 501, "st_nlink": 2},
])
def test_unsafe_lock_inode_is_rejected(fields):
    lock, hooks = fake_lock(statter=Mock(return_value=Mock(**fields)))

    assert lock.acquire() is False

    hooks["locker"].assert_not_called()
    hooks["closer"].assert_called_once_with(91)
    lock.release()
    hooks["closer"].assert_called_once_with(91)


@pytest.mark.parametrize("error_number", [
    guard.errno.ELOOP,
    guard.errno.EACCES,
    guard.errno.EPERM,
    guard.errno.EISDIR,
    guard.errno.ENXIO,
])
def test_unsafe_lock_path_is_skipped(error_number):
    lock, hooks = fake_lock(
        opener=Mock(side_effect=OSError(error_number, "unsafe lock path"))
    )

    assert lock.acquire() is False

    hooks["statter"].assert_not_called()
    hooks["locker"].assert_not_called()
    hooks["closer"].assert_not_called()


def test_descriptor_is_closed_even_when_unlock_fails():
    locker = Mock(side_effect=[None, OSError("unlock failed")])
    lock, hooks = fake_lock(locker=locker)
    assert lock.acquire()

    with pytest.raises(OSError):
        lock.release()

    hooks["closer"].assert_called_once_with(91)


def test_busy_lock_returns_success_without_auditing():
    system = make_host()
    system.lock.acquire.return_value = False

    result = guard.Guard(guard.Config(mode="enforce"), system).run()

    assert result.status == "SKIPPED_LOCKED"
    assert result.exit_code == 0
    system.getenv.assert_not_called()
    system.processes.assert_not_called()
    system.terminate.assert_not_called()
    system.unsetenv.assert_not_called()
    system.lock.release.assert_not_called()


def test_unexpected_lock_acquisition_failure_is_reported():
    system = make_host()
    system.lock.acquire.side_effect = OSError(guard.errno.EIO, "cannot open")

    result = guard.Guard(guard.Config(), system).run()

    assert result.status == "ERROR"
    assert result.errors == ["LOCK_FAILED"]
    assert result.exit_code == 1
    system.getenv.assert_not_called()


def test_shared_budget_stops_actions_and_releases_lock():
    system = make_host()
    clock = [0.0]
    system.monotonic = lambda: clock[0]
    system.getenv.side_effect = lambda name, budget: (
        "http://localhost:44445" if name == "HTTP_PROXY" else None
    )
    system.listener_count.return_value = 0
    system.probe.return_value = False

    def advance(delay, budget):
        clock[0] = 2.0
        budget.check()

    system.pause.side_effect = advance

    result = guard.Guard(
        guard.Config(mode="enforce", run_timeout_s=1), system
    ).run()

    assert result.status == "TIMEOUT"
    assert result.exit_code == 1
    system.listener_count.assert_called_once_with(44445, ANY)
    system.probe.assert_called_once_with(44445, ANY)
    system.processes.assert_not_called()
    system.unsetenv.assert_not_called()
    system.terminate.assert_not_called()
    system.lock.release.assert_called_once_with()


def test_pause_does_not_sleep_past_deadline():
    sleeper = Mock()
    system = guard.System(guard.Config(), sleeper=sleeper, lock=Mock())

    with pytest.raises(guard.BudgetExpired):
        system.pause(0.4, guard.Budget(0.3, lambda: 0))

    sleeper.assert_not_called()


def test_command_timeout_is_capped_by_remaining_budget():
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    system = guard.System(
        guard.Config(command_timeout_s=10), runner=runner, lock=Mock()
    )

    assert system.getenv("HTTP_PROXY", guard.Budget(0.3, lambda: 0)) is None

    options = runner.call_args.kwargs
    assert options["timeout"] == pytest.approx(0.3)
    assert options["stdin"] == subprocess.DEVNULL
    assert options.get("shell", False) is False
    assert options["env"]["LC_ALL"] == "C"
    assert options["env"]["LANG"] == "C"


def test_probe_timeout_is_capped_by_remaining_budget():
    connector = Mock(return_value=False)
    system = guard.System(
        guard.Config(connect_timeout_s=10), connector=connector, lock=Mock()
    )

    assert system.probe(44445, guard.Budget(0.25, lambda: 0)) is False

    connector.assert_called_once_with("127.0.0.1", 44445, 0.25)


@pytest.mark.parametrize("exception", [
    FileNotFoundError("missing command"),
    subprocess.TimeoutExpired("ps", 1),
])
def test_command_failure_is_a_safe_audit_error(exception):
    runner = Mock(side_effect=exception)
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    with pytest.raises(guard.GuardError):
        system.processes(guard.Budget(24, lambda: 0))


def test_process_snapshot_parses_start_time_and_command():
    runner = Mock(return_value=subprocess.CompletedProcess(
        [], 0, "8123 1 ?? Tue Jan  2 03:04:05 2024 /opt/bin/droid\n", ""
    ))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    rows = system.processes(guard.Budget(24, lambda: 0))

    assert len(rows) == 1
    assert rows[0].identity == (8123, "Tue Jan 2 03:04:05 2024")
    assert rows[0].ppid == 1
    assert rows[0].tty == "??"
    assert rows[0].command == "/opt/bin/droid"
    assert tuple(guard.time.localtime(rows[0].started_at)[:6]) == (
        2024, 1, 2, 3, 4, 5
    )


@pytest.mark.parametrize("text", [
    "garbage\n",
    "8123 1 ?? Tue Jan 99 03:04:05 2024 /opt/droid\n",
    "8123 1 ?? Tue Jan 2 25:04:05 2024 /opt/droid\n",
    "8123 1 ?? Unknown Jan 2 03:04:05 2024 /opt/droid\n",
    "8123 1 ?? Tue Unknown 2 03:04:05 2024 /opt/droid\n",
    "0 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n",
    "8123 -1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n",
    "8123 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\0\n",
])
def test_malformed_process_snapshot_rows_are_skipped(text):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    assert system.processes(guard.Budget(24, lambda: 0)) == []


@pytest.mark.parametrize("text", [
    "8123 2 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n",
    "8123 0 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n",
    "8123 1 ttys001 Tue Jan 2 03:04:05 2024 /opt/droid\n",
    "8123 1 ?? Tue Jan 2 03:04:05 2024 /usr/bin/curl\n",
    "8123 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid-backup\n",
])
def test_non_candidate_process_snapshot_rows_are_skipped(text):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    assert system.processes(guard.Budget(24, lambda: 0)) == []


def test_duplicate_process_snapshot_rows_are_skipped():
    text = (
        "8123 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n"
        "8123 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n"
    )
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    rows = system.processes(guard.Budget(24, lambda: 0))

    assert len(rows) == 1
    assert rows[0].identity == (8123, "Tue Jan 2 03:04:05 2024")


def test_invalid_and_unrelated_rows_do_not_hide_valid_candidates():
    text = (
        "garbage\n"
        "8123 1 ?? Tue Jan 99 03:04:05 2024 /opt/droid\n"
        "9000 2 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n"
        "9001 1 ?? Tue Jan 2 03:04:05 2024 /usr/bin/curl\n"
        "8123 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n"
        "9002 1 ?? Tue Jan 2 03:04:05 2024 /opt/proxyrack-forward.py\n"
    )
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    rows = system.processes(guard.Budget(24, lambda: 0))

    assert [row.pid for row in rows] == [8123, 9002]


@pytest.mark.parametrize("text", [
    "",
    "garbage\n",
    "8123 1 ?? Tue Jan 99 03:04:05 2024 /opt/droid\n",
    "8124 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n",
])
def test_process_lookup_without_valid_matching_row_returns_none(text):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    assert system.process(8123, guard.Budget(24, lambda: 0)) is None


def test_process_lookup_skips_malformed_rows():
    text = (
        "garbage\n"
        "8123 1 ?? Tue Jan 2 03:04:05 2024 /opt/droid\n"
    )
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    process = system.process(8123, guard.Budget(24, lambda: 0))

    assert process is not None
    assert process.identity == (8123, "Tue Jan 2 03:04:05 2024")


@pytest.mark.parametrize("text,expected", [
    ("PID\tStatus\tLabel\n", set()),
    ("PID\tStatus\tLabel\n-\t0\tidle.agent\n", set()),
    ("PID\tStatus\tLabel\n8123\t0\tactive.agent\n", {8123}),
])
def test_launchctl_listing_parser(text, expected):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    assert system.launch_pids(guard.Budget(24, lambda: 0)) == expected


@pytest.mark.parametrize("text", [
    "", "unknown header\n", "PID Status Label\nbroken\n",
    "PID Status Label\nzero 0 agent\n",
    "PID Status Label\n0 0 agent\n",
])
def test_invalid_launchctl_listing_is_rejected(text):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, text, ""))
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    with pytest.raises(guard.GuardError):
        system.launch_pids(guard.Budget(24, lambda: 0))


@pytest.mark.parametrize("text,expected", [
    ("/usr/bin/python3 /opt/proxyrack-forward.py",
     ("/usr/bin/python3", "/opt/proxyrack-forward.py")),
    ('python3 "/a path/proxyrack-forward.py"',
     ("python3", "/a path/proxyrack-forward.py")),
    ("python3 '/a path/proxyrack-forward.py'",
     ("python3", "/a path/proxyrack-forward.py")),
    ("python3 /a\\ path/proxyrack-forward.py",
     ("python3", "/a path/proxyrack-forward.py")),
])
def test_argument_rendering_parser(text, expected):
    assert guard._split_arguments(text) == expected


@pytest.mark.parametrize("text", [
    'python3 "unfinished',
    "python3 trailing\\",
    "python3 a\nb",
    "python3 a\0b",
])
def test_ambiguous_argument_rendering_is_rejected(text):
    with pytest.raises(guard.GuardError):
        guard._split_arguments(text)


@pytest.mark.parametrize("method", ["getenv", "unsetenv"])
def test_environment_backend_rejects_names_outside_scope(method):
    runner = Mock()
    system = guard.System(guard.Config(), runner=runner, lock=Mock())

    with pytest.raises(guard.GuardError):
        getattr(system, method)("NO_PROXY", guard.Budget(24, lambda: 0))

    runner.assert_not_called()


@pytest.mark.parametrize("text,expected", [
    ("", ""),
    ('a"b', 'a\\"b'),
    ("a\\b", "a\\\\b"),
    ("a\rb\nc", "a b c"),
    ('a\\"b\r\nc', 'a\\\\\\"b  c'),
])
def test_applescript_string_escaping(text, expected):
    assert guard._escape_applescript(text) == expected


def test_notification_escapes_message_and_title():
    title = 'Title "\\\r\nend'
    message = 'Message "\\\r\nend'
    child = Mock()
    spawner = Mock(return_value=child)
    system = guard.System(
        guard.Config(notification_title=title), spawner=spawner, lock=Mock(),
    )

    system.notify(message)

    safe_title = 'Title \\"\\\\  end'
    safe_message = 'Message \\"\\\\  end'
    spawner.assert_called_once_with(
        [
            guard.OSASCRIPT, "-e",
            f'display notification "{safe_message}" with title "{safe_title}"',
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    child.wait.assert_not_called()
    child.communicate.assert_not_called()


def test_main_prints_machine_readable_status(capsys):
    system = make_host()
    system.lock.acquire.return_value = False

    code = guard.main(["--mode=enforce"], system=system, environ={})

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {
        "mode": "enforce", "status": "SKIPPED_LOCKED",
        "events": [], "errors": [],
    }


def test_lock_release_failure_is_visible():
    system = make_host()
    system.lock.release.side_effect = OSError("failed")

    result = guard.Guard(guard.Config(), system).run()

    assert result.status == "ERROR"
    assert result.errors == ["LOCK_RELEASE_FAILED"]

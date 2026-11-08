"""Cycle 7: реестр групп потомков, безопасная зачистка без переиспользования PID, барьер spawn."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import pytest

import core.proc_groups as pg

SLEEP = [sys.executable, "-c", "import time; time.sleep(60)"]
ORPHAN_PARENT = (
    "sleep 60 & echo $!; exit 0"  # лидер выходит, потомок остаётся в его группе
)


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    pg.reset_proc_groups()
    pg.spawn_registered.set_blocked(False)  # type: ignore[attr-defined]
    yield
    pg.spawn_registered.set_blocked(False)  # type: ignore[attr-defined]
    for proc in pg.live_proc_groups():
        pg.spawn_registered.unregister(proc)  # type: ignore[attr-defined]
    pg.reset_proc_groups()


def pid_gone(pid: int, timeout_s: float = 3.0) -> bool:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.02)
    return False


def spawn_orphan_parent() -> tuple[Any, int]:
    proc = pg.spawn_registered(
        ["sh", "-c", ORPHAN_PARENT], stdout=subprocess.PIPE, text=True
    )
    assert proc.stdout is not None
    child = int(proc.stdout.readline())
    time.sleep(0.3)  # лидер вышел, но НЕ собран: зомби держит свой PID
    return proc, child


def test_unreaped_leader_with_live_child_is_killed_then_reaped() -> None:
    """F-001: несобранный лидер (зомби) держит PID; группа гасится ДО `poll()`, затем лидер собирается."""
    proc, child = spawn_orphan_parent()
    assert proc.returncode is None  # ещё не собран
    pg.terminate_proc_groups_parallel([proc], 1.0, 1.0)
    assert pid_gone(child), "сирота группы пережил зачистку"
    assert proc.returncode is not None  # лидер собран после сигналов
    assert proc.pid not in [p.pid for p in pg.live_proc_groups()]


def test_already_reaped_leader_is_never_signalled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLOCKER-SAFETY F-001: собранный лидер (`returncode is not None`) — PID мог уйти чужой группе."""
    proc = pg.spawn_registered(["true"])
    proc.wait()
    assert proc.returncode is not None
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(pg.os, "killpg", lambda pgid, sig: sent.append((pgid, sig)))
    pg.terminate_proc_groups_parallel([proc], 0.2, 0.2)
    assert sent == []  # ни TERM, ни KILL, ни даже проба `killpg(pgid, 0)`
    assert pg.live_proc_groups() == []


def test_registry_never_retains_reaped_processes() -> None:
    """RW-010: в реестре только живые несобранные лидеры; завершившийся выбывает при чтении."""
    quick = pg.spawn_registered(["true"])
    quick.wait()
    sleeper = pg.spawn_registered(SLEEP)
    live = pg.live_proc_groups()
    assert [p.pid for p in live] == [sleeper.pid]
    assert all(p.returncode is None for p in live)


def test_registry_read_never_reaps_or_kills() -> None:
    """F-001 (Seat 1/3): чтение реестра не зовёт `poll()` — вышедший, но несобранный лидер остаётся, сироты живы."""
    proc, child = spawn_orphan_parent()
    assert [p.pid for p in pg.live_proc_groups()] == [proc.pid]
    assert proc.returncode is None  # `waitpid` не вызывался
    os.kill(child, 0)  # сирота жив
    pg.terminate_proc_groups_parallel([proc], 1.0, 1.0)
    assert pid_gone(child) and proc.returncode is not None


def test_no_sigkill_for_leader_reaped_after_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seat 1 F-001.2: рабочий поток собрал лидера после SIGTERM — PID свободен, SIGKILL ему не шлём."""
    sent: list[tuple[int, int]] = []

    class Leader:
        pid, returncode = 77_001, None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    leader = Leader()
    monkeypatch.setattr(pg, "_group_alive", lambda _pgid: True)

    def fake_killpg(pgid: int, sig: int) -> None:
        sent.append((pgid, sig))
        leader.returncode = -15  # `proc.wait()` рабочего потока собрал лидера

    monkeypatch.setattr(pg.os, "killpg", fake_killpg)
    pg.terminate_proc_groups_parallel([leader], 0.05, 0.05)
    assert [sig for _, sig in sent] == [15]  # только SIGTERM


def test_reap_phase_shares_one_deadline_for_all_leaders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-003.3 (Seat 1/2/3): сбор лидеров делит ОДИН дедлайн `kill_wait_s`, а не `kill_wait_s` на процесс."""
    waits: list[float] = []

    class Stuck:
        returncode = None

        def __init__(self, pid: int) -> None:
            self.pid = pid

        def wait(self, timeout: float | None = None) -> int:
            waits.append(timeout or 0.0)
            time.sleep(timeout or 0.0)
            raise subprocess.TimeoutExpired("x", timeout or 0.0)

    procs = [Stuck(78_000 + i) for i in range(20)]
    monkeypatch.setattr(pg, "_group_alive", lambda _pgid: True)
    monkeypatch.setattr(pg.os, "killpg", lambda *_a: None)
    start = time.monotonic()
    pg.terminate_proc_groups_parallel(procs, 0.05, 0.4)
    assert time.monotonic() - start < 0.05 + 0.4 + 0.5  # не 20 * 0.4
    assert sum(waits) <= 0.45


def test_unregister_removes_entry_even_when_leader_already_reaped() -> None:
    proc = pg.spawn_registered(["true"])
    proc.wait()  # `communicate()` этого же хода собрал лидера
    pg.register_proc_group(proc)
    pg.spawn_registered.unregister(proc)  # type: ignore[attr-defined]
    assert proc.pid not in [p.pid for p in pg.live_proc_groups()]
    assert pg.terminate_proc_groups_parallel([], 0.1, 0.1) is None


def test_spawn_barrier_rejects_new_children_during_shutdown() -> None:
    """F-002: после `set_blocked(True)` проснувшийся запрос не может породить процесс."""
    spawn = pg.spawn_registered
    spawn.set_blocked(True)  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="shutting down"):
        spawn(SLEEP)
    assert pg.live_proc_groups() == []
    spawn.set_blocked(False)  # type: ignore[attr-defined]
    proc = spawn(SLEEP)
    assert [p.pid for p in pg.live_proc_groups()] == [proc.pid]


def test_unregister_terminates_group_and_reaps_leader() -> None:
    proc, child = spawn_orphan_parent()
    pg.spawn_registered.unregister(proc)  # type: ignore[attr-defined]
    assert proc.returncode is not None and pid_gone(child)
    assert pg.live_proc_groups() == []
    done = pg.spawn_registered(["true"])
    done.wait()
    pg.spawn_registered.unregister(done)  # type: ignore[attr-defined]  # собранный: без сигналов


def test_public_surface_stays_within_six_entry_points() -> None:
    import ast
    from pathlib import Path

    tree = ast.parse(Path(pg.__file__).read_text(encoding="utf-8"))
    public = [
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
    ]
    assert len(public) <= 6 and len(Path(pg.__file__).read_text().splitlines()) <= 300

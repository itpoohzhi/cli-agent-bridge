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


def test_finished_leader_orphans_are_cleaned_when_registry_observes_exit() -> None:
    """RW-010: сироты завершившегося лидера гасятся в момент сбора, drain не ждёт их до таймаута."""
    proc, child = spawn_orphan_parent()
    assert pg.live_proc_groups() == []  # `poll()` собрал лидера и убил его группу
    assert proc.returncode is not None
    assert pid_gone(child)


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

from __future__ import annotations

# Ожидание `flock` ограничено монотонным дедлайном (не числом итераций); часы подменены, зависание невозможно.

import fcntl
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import catalog_promote as promote  # noqa: E402


class FakeClock:
    """Монотонные часы: `sleep` двигает время; зацикливание обрывается AssertionError."""

    def __init__(self, on_sleep: Callable[[int], None] | None = None) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []
        self.on_sleep = on_sleep

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        assert len(self.sleeps) < 100, "runaway lock wait"
        if self.on_sleep:
            self.on_sleep(len(self.sleeps))


@pytest.fixture
def held_lock(tmp_path: Path):
    fd = os.open(tmp_path / promote.LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    yield fd
    os.close(fd)


def _use(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    monkeypatch.setattr(promote, "time", SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep))


@pytest.mark.parametrize(
    "policy,sleeps",
    [((1.0, 0.25), [0.25] * 4), ((0.0, 5.0), []), ((0.3, 1.0), [1.0])],
)
def test_busy_lock_waits_until_monotonic_deadline_then_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, held_lock: int, policy: tuple[float, float], sleeps: list[float]
) -> None:
    clock = FakeClock()
    _use(monkeypatch, clock)
    with pytest.raises(promote.PromoteError, match="lifecycle_lock_busy"):
        with promote.lifecycle_lock(tmp_path, promote.LockPolicy(*policy)):
            pass
    assert clock.sleeps == sleeps


def test_lock_released_during_wait_is_acquired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, held_lock: int) -> None:
    clock = FakeClock(lambda n: fcntl.flock(held_lock, fcntl.LOCK_UN) if n == 2 else None)
    _use(monkeypatch, clock)
    entered = []
    with promote.lifecycle_lock(tmp_path, promote.LockPolicy(5.0, 0.25)):
        entered.append(True)
    assert entered == [True] and clock.sleeps == [0.25, 0.25]

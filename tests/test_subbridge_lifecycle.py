"""Cycle 7: бюджет таймеров под `ExitTimeOut` (RW-003), keep-alive при drain, подметание при `force_kill`."""

from __future__ import annotations

import io
import signal
import subprocess
import sys
from typing import Any

import pytest

import core.proc_groups as pg
import core.subbridge_lifecycle as mod
from core.subbridge_config import SubbridgeDrainConfig

CASES = [
    {"BRIDGE_EXIT_TIMEOUT_S": "180", "BRIDGE_DRAIN_FLUSH_GRACE_S": "200"},
    {"BRIDGE_EXIT_TIMEOUT_S": "180", "BRIDGE_KILL_TERM_GRACE_S": "200"},
    {
        "BRIDGE_EXIT_TIMEOUT_S": "180",
        "BRIDGE_KILL_WAIT_S": "500",
        "BRIDGE_DRAIN_FLUSH_GRACE_S": "500",
    },
    {
        "BRIDGE_EXIT_TIMEOUT_S": "10",
        "BRIDGE_KILL_TERM_GRACE_S": "200",
        "BRIDGE_DRAIN_FLUSH_GRACE_S": "200",
    },
    {"BRIDGE_EXIT_TIMEOUT_S": "5"},
    {
        "BRIDGE_EXIT_TIMEOUT_S": "100",
        "BRIDGE_SHORT_EXIT_TIMEOUT_S": "1000",
        "BRIDGE_KILL_WAIT_S": "90",
    },
    {"BRIDGE_EXIT_TIMEOUT_S": "1", "BRIDGE_DRAIN_SAFETY_MARGIN_S": "50"},
]


@pytest.mark.parametrize("env", CASES)
def test_drain_plus_tail_always_fits_exit_timeout(env: dict[str, str]) -> None:
    """F-003 / RW-003: drain + (TERM+KILL+flush) < `ExitTimeOut` при ЛЮБЫХ значениях env."""
    cfg = SubbridgeDrainConfig.from_env(env)
    timers = cfg.effective_timers()
    assert all(t >= 0 for t in timers)
    assert cfg.effective_drain_timeout_s + sum(timers) < cfg.exit_timeout_s


def test_defaults_are_not_squeezed_and_drain_is_168s() -> None:
    cfg = SubbridgeDrainConfig.from_env({"BRIDGE_EXIT_TIMEOUT_S": "180"})
    assert cfg.effective_timers() == (2.0, 3.0, 2.0)
    assert cfg.effective_drain_timeout_s == pytest.approx(
        110.0
    )  # `drain_timeout_s` < бюджета 168 с
    big = SubbridgeDrainConfig.from_env(
        {"BRIDGE_EXIT_TIMEOUT_S": "180", "BRIDGE_DRAIN_TIMEOUT_S": "999"}
    )
    assert big.effective_drain_timeout_s == pytest.approx(168.0)


def test_oversized_tail_is_scaled_proportionally() -> None:
    cfg = SubbridgeDrainConfig.from_env(
        {"BRIDGE_EXIT_TIMEOUT_S": "180", "BRIDGE_DRAIN_FLUSH_GRACE_S": "200"}
    )
    term, kill, flush = cfg.effective_timers()
    assert sum((term, kill, flush)) == pytest.approx(180 - cfg.margin_s - 0.05)
    assert flush / term == pytest.approx(100.0)  # пропорции исходных 200:2 сохранены


def test_zero_drain_timeout_is_respected_and_threshold_comes_from_env_arg() -> None:
    cfg = SubbridgeDrainConfig.from_env(
        {"BRIDGE_DRAIN_TIMEOUT_S": "0", "BRIDGE_SHORT_EXIT_TIMEOUT_S": "42"}
    )
    assert cfg.drain_timeout_s == 0.0 and cfg.effective_drain_timeout_s == 0.0
    assert (
        cfg.short_exit_threshold_s == 42.0
    )  # из переданного `env`, а не из `os.environ`


class _Handler:
    """Минимальный двойник `BaseHTTPRequestHandler` для `install()`."""

    def __init__(self, path: str, life: Any, drain_inside: bool) -> None:
        self.path, self.close_connection, self.wfile = path, False, io.BytesIO()
        self.life, self.drain_inside = life, drain_inside
        self.status = 0

    def send_response(self, code: int) -> None:
        self.status = code

    def send_header(self, *_a: Any) -> None: ...
    def end_headers(self) -> None: ...

    def do_GET(self) -> None:
        self.status = 200

    def do_POST(self) -> None:
        if self.drain_inside:
            self.life.handle_signal(signal.SIGTERM)  # SIGTERM пришёл посреди хода
        self.status = 200


def make_life() -> Any:
    return mod.SubbridgeLifecycle(
        SubbridgeDrainConfig(), mod.SubbridgeHooks(procs_fn=lambda: [])
    )


def test_install_closes_keep_alive_connection_when_draining_after_request() -> None:
    """Seat 2 F-005.1: запрос, завершившийся в drain, не оставляет keep-alive соединение."""
    life = make_life()
    cls = life.install(type("H", (_Handler,), {}))
    calm = cls("/v1/chat/completions", life, False)
    cls.do_POST(calm)
    assert calm.status == 200 and calm.close_connection is False
    mid = cls("/v1/chat/completions", life, True)
    cls.do_POST(mid)
    assert mid.status == 200 and mid.close_connection is True
    later = cls("/v1/models", life, False)
    cls.do_GET(later)  # drain уже идёт: и GET закрывает соединение
    assert later.close_connection is True


def test_handle_signal_stores_signum_without_conversion() -> None:
    life = make_life()
    life.handle_signal(signal.SIGTERM)
    assert life.last_signal is signal.SIGTERM  # без `int()` в обработчике (RW-007)
    assert life._signal_received and life._shutdown_requested


def test_force_kill_blocks_spawn_and_resweeps_late_children() -> None:
    """F-002: после `force_kill` новых потомков нет, а поздно зарегистрированный гасится повторным проходом."""
    life = mod.SubbridgeLifecycle(
        SubbridgeDrainConfig(kill_term_grace_s=0.2, kill_wait_s=0.5),
        mod.SubbridgeHooks(procs_fn=pg.live_proc_groups),
    )
    try:
        life.force_kill()
        with pytest.raises(RuntimeError):
            pg.spawn_registered([sys.executable, "-c", "pass"])
        late = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        pg.register_proc_group(late)  # «проснувшийся» ход успел до барьера
        life.force_kill()
        assert late.returncode is not None and late.returncode < 0
    finally:
        life.reset()  # снимает барьер для остальных тестов
        pg.reset_proc_groups()
    assert pg.spawn_registered(["true"]).wait() == 0


def test_force_kill_merges_registry_and_ps_groups_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[int]] = []
    monkeypatch.setattr(
        mod,
        "terminate_proc_groups_parallel",
        lambda procs, *_a: seen.append([p.pid for p in procs]),
    )
    monkeypatch.setattr(
        mod, "child_process_groups", lambda: [pg._ChildGroup(111), pg._ChildGroup(222)]
    )
    own = [pg._ChildGroup(222), pg._ChildGroup(333)]
    life = mod.SubbridgeLifecycle(
        SubbridgeDrainConfig(), mod.SubbridgeHooks(procs_fn=lambda: own)
    )
    life.force_kill()
    life.reset()
    assert sorted(seen[0]) == [111, 222, 333]

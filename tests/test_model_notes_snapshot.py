"""L1: bounded reader, singleflight, непродлеваемый LKG и долговечный CAS."""

from __future__ import annotations

import errno
import json
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import model_notes_snapshot as mod  # noqa: E402

VALID = "## 1. Блокировки\n| Модель | Статус | Причина |\n|---|---|---|\n| a | BANNED | test |\n"
Factory = Callable[..., mod.ModelNotesSnapshotManager]


@pytest.fixture
def make(tmp_path: Path) -> Iterator[Factory]:
    owned: list[mod.ModelNotesSnapshotManager] = []
    source = tmp_path / "notes.md"
    source.write_text(VALID)

    def factory(**over: Any) -> mod.ModelNotesSnapshotManager:
        env = {"MODEL_NOTES_PATH": str(source), "BRIDGE_STATE_DIR": str(tmp_path / "state")} | over
        manager = mod.ModelNotesSnapshotManager(env)
        owned.append(manager)
        return manager

    yield factory
    for manager in owned:
        manager.close()
        assert manager.stopped.wait(2)
        manager._timer.join()
        if manager._worker is not None:
            assert manager._done.wait(2)
            manager._worker.join()


def refresh(manager: mod.ModelNotesSnapshotManager) -> None:
    if manager._worker is not None:
        assert manager._done.wait(2)
        manager._worker.join()
    manager._refresh()


@pytest.mark.parametrize("value", [True, False, None, "", "bad", "nan", "inf", -1, 301])
@pytest.mark.parametrize("bounds", [(30, 5, 300), (2, 0.01, 10), (60, 0, 60)])
def test_numeric_invalid_defaults(value: object, bounds: tuple[float, float, float]) -> None:
    assert mod.nfr_scale(value, *bounds) == bounds[0]


@pytest.mark.parametrize("bounds", [(30, 5, 300), (2, 0.01, 10), (60, 0, 60)])
def test_numeric_boundaries(bounds: tuple[float, float, float]) -> None:
    for value in bounds[1:]:
        assert mod.nfr_scale(str(value), *bounds) == value


def test_config_and_warning_once(make: Callable[..., Any], capsys: pytest.CaptureFixture[str]) -> None:
    manager = make(MODEL_NOTES_REFRESH_INTERVAL_S="300", MODEL_NOTES_STALE_GRACE_S="61")
    assert (manager.refresh_interval_s, manager.read_timeout_s, manager.stale_grace_s) == (300, 2, 60)
    refresh(manager)
    assert capsys.readouterr().err.count("STALE_GRACE") == 1


@pytest.mark.parametrize("value", ["", "/no/such/selected-notes", "bad\0path"])
def test_present_source_never_falls_back(make: Callable[..., Any], value: str, tmp_path: Path) -> None:
    manager = make(MODEL_NOTES_PATH=value, BRIDGE_MODEL_NOTES_PATH=str(tmp_path / "notes.md"))
    assert manager.status == "FAILED_CLOSED"


def test_default_and_secondary_source(make: Factory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod.Path, "home", lambda: tmp_path)
    assert mod.select_source({}) == str(tmp_path / "Мой диск/Context/model-notes.md")
    assert mod.select_source({"BRIDGE_MODEL_NOTES_PATH": "secondary"}) == "secondary"
    manager = make()
    assert manager.status == "OK" and manager.snapshot is not None
    assert manager.snapshot.rules[0].model == "a"


def test_initial_failure_ignores_disk_lkg_and_recovers(make: Callable[..., Any], tmp_path: Path) -> None:
    assert make().status == "OK"
    source = tmp_path / "notes.md"
    source.unlink()
    manager = make()
    assert manager.status == "FAILED_CLOSED" and manager.snapshot is None
    source.write_text(VALID)
    refresh(manager)
    assert manager.status == "OK"


def test_hung_initial_bounded_singleflight(make: Callable[..., Any], monkeypatch: pytest.MonkeyPatch) -> None:
    release, entered = threading.Event(), threading.Event()
    original = mod.read_model_notes_file

    def hung(path: Any, *args: Any) -> str:
        if str(path).endswith("notes.md"):
            entered.set()
            assert release.wait(2)
        return original(path, *args)

    monkeypatch.setattr(mod, "read_model_notes_file", hung)
    try:
        start = mod.time.perf_counter()
        manager = make(MODEL_NOTES_READ_TIMEOUT_S=".01")
        assert mod.time.perf_counter() - start < 0.5
        assert entered.is_set() and manager.status == "FAILED_CLOSED"
        worker = manager._worker
        manager._done.set()
        for _ in range(20):
            manager.maybe_trigger_refresh_async()
            manager._refresh()
        assert manager.in_flight_workers == 1 and manager._worker is worker
    finally:
        release.set()
    refresh(manager)
    assert manager.status == "OK" and manager._fault_since is None


@pytest.mark.parametrize("error", [PermissionError(errno.EACCES, "denied"), TimeoutError("hang")])
def test_transient_grace(make: Factory, monkeypatch: pytest.MonkeyPatch, error: OSError) -> None:
    manager = make()
    now = [100.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: now[0])
    failure = Mock(side_effect=error)
    monkeypatch.setattr(mod, "read_model_notes_file", failure)
    refresh(manager)
    assert manager.status == "OK"
    now[0] = 159.99
    refresh(manager)
    assert manager.status == "OK" and manager._fault_since == 100
    now[0] = 160
    assert manager.status == "FAILED_CLOSED" and manager.snapshot is None
    refresh(manager)
    assert manager._fault_since == 100
    assert manager.worker_error is error


@pytest.mark.parametrize("text", [None, "", "malformed", "<!-- EXPIRY: 2000-01-01 00:00 UTC -->\n" + VALID])
def test_hard_fault_immediate(make: Callable[..., Any], tmp_path: Path, text: str | None) -> None:
    manager = make()
    source = tmp_path / "notes.md"
    source.unlink() if text is None else source.write_text(text)
    refresh(manager)
    assert manager.status == "FAILED_CLOSED" and manager.snapshot is None


def test_request_path_no_io_or_wait(make: Callable[..., Any], monkeypatch: pytest.MonkeyPatch) -> None:
    manager = make()
    manager._next_refresh = 0
    forbidden = Mock(side_effect=AssertionError("request I/O"))
    with monkeypatch.context() as scoped:
        scoped.setattr(manager._wake, "set", Mock())
        scoped.setattr(mod, "read_model_notes_file", forbidden)
        scoped.setattr(mod.os, "open", forbidden)
        scoped.setattr(threading.Thread, "start", forbidden)
        manager.maybe_trigger_refresh_async()
        assert manager.status == "OK" and manager.snapshot is not None
    forbidden.assert_not_called()


def test_timer_recovers_without_requests(make: Callable[..., Any], tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.unlink()
    manager = make()
    source.write_text(VALID)
    observed = threading.Event()
    original = manager._refresh

    def observe() -> None:
        original()
        observed.set()

    manager._refresh = observe
    manager._next_refresh = mod.time.monotonic() + 0.01
    manager._wake.set()
    assert observed.wait(2)
    assert manager.status == "OK"


def test_durable_order_and_failed_write(make: Callable[..., Any], monkeypatch: pytest.MonkeyPatch) -> None:
    manager = make()
    before = manager.snapshot
    events: list[str] = []
    real_sync, real_replace = mod.os.fsync, mod.os.replace

    def sync(fd: int) -> None:
        assert manager.snapshot is before
        events.append("sync")
        real_sync(fd)

    def replace(*args: Any) -> None:
        assert manager.snapshot is before
        events.append("replace")
        real_replace(*args)

    monkeypatch.setattr(mod.os, "fsync", sync)
    monkeypatch.setattr(mod.os, "replace", replace)
    refresh(manager)
    assert events == ["sync", "replace", "sync"]
    before = manager.snapshot
    monkeypatch.setattr(mod.os, "replace", Mock(side_effect=OSError("write failed")))
    refresh(manager)
    assert manager.snapshot is before and isinstance(manager.worker_error, OSError)


@pytest.mark.parametrize("replacement", ["<!-- GENERATION: 99 -->\n", "<!-- GENERATION: 100 -->\n\n"])
def test_generation_epoch_cas(make: Factory, tmp_path: Path, replacement: str) -> None:
    manager = make()
    path = manager.snapshot_path
    base = path.read_text()
    document = mod.parse_model_notes(VALID)
    refresh(manager)
    assert json.loads(path.read_text())["epoch"] == json.loads(base)["epoch"] + 1
    with pytest.raises(mod.SnapshotConflict):
        manager._publish(document, VALID, base)
    source = tmp_path / "notes.md"
    source.write_text("<!-- GENERATION: 100 -->\n" + VALID)
    refresh(manager)
    assert manager.status == "OK"
    source.write_text(replacement + VALID)
    refresh(manager)
    assert manager.status == "FAILED_CLOSED"


def test_size_and_function_gates() -> None:
    from tests.test_transport_modularity import exceeds, functions, metrics

    for path in (Path(__file__), Path(str(mod.__file__))):
        data = path.read_bytes()
        assert len(data.splitlines()) <= 260
        assert not {n: metrics(f) for n, f in functions(data).items() if exceeds(metrics(f))}


def test_fatal_exception_evidence(make: Factory, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = make()
    refresh(manager)
    failure = KeyboardInterrupt("fatal evidence")
    monkeypatch.setattr(mod, "read_model_notes_file", Mock(side_effect=failure))
    with pytest.raises(KeyboardInterrupt):
        manager._work()
    assert manager.worker_error is failure and failure.__traceback__ is not None
    assert manager.status == "FAILED_CLOSED"


def test_expiry_checked_without_refresh(make: Factory, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace
    from datetime import datetime, timezone

    manager = make()
    assert manager.snapshot is not None
    manager._notes = replace(manager.snapshot, expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(mod, "read_model_notes_file", Mock(side_effect=AssertionError("I/O")))
    assert manager.status == "FAILED_CLOSED" and manager.snapshot is None

"""C1-NF: совместимый фасад, stderr-only alias и синхронный startup."""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import model_notes_filter as mod  # noqa: E402
from core import model_notes_snapshot as snapshots  # noqa: E402

Notes = mod.ModelNotesFilter
VALID = (
    "## 1. Блокировки\n| Модель | Статус | Причина |\n|---|---|---|\n"
    "| a | BANNED | test |\n| b-high / cli | TEMP OFF | test |\n"
    "| family* | RETIRED | test |\n"
)


@pytest.fixture
def notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Notes]:
    path = tmp_path / "notes.md"
    path.write_text(VALID, encoding="utf-8")
    monkeypatch.delenv("MODEL_NOTES_PATH", raising=False)
    monkeypatch.setenv("BRIDGE_MODEL_NOTES_PATH", str(path))
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path / "state"))
    value = mod.ModelNotesFilter(path=path, ttl_s=5)
    yield value
    value.close()
    assert value.manager.stopped.wait(2)
    value.manager._timer.join()
    if value.manager._worker is not None:
        value.manager._worker.join(2)
        assert not value.manager._worker.is_alive()


@pytest.mark.parametrize(
    ("model", "transport", "effort", "blocked"),
    [
        ("a", None, None, True),
        ("allowed", None, None, False),
        ("family-member", None, None, True),
        ("b", "cli", "high", True),
        ("b-high", "cli", None, True),
        ("b", "other", "high", False),
        ("b", "cli", "low", False),
    ],
)
def test_compatibility(
    notes: Notes,
    model: str,
    transport: str | None,
    effort: str | None,
    blocked: bool,
) -> None:
    assert notes.is_blocked(model, transport, effort) is blocked
    assert notes.health_state() == "OK" and not notes.is_failed_closed()
    assert notes.path.name == "notes.md" and notes.ttl_s == 5


def test_no_request_io(notes: Notes, monkeypatch: pytest.MonkeyPatch) -> None:
    wake = Mock()
    forbidden = Mock(side_effect=AssertionError("request I/O or wait"))
    monkeypatch.setattr(notes.manager, "maybe_trigger_refresh_async", wake)
    monkeypatch.setattr(snapshots, "read_model_notes_file", forbidden)
    with monkeypatch.context() as scoped:
        scoped.setattr(threading.Event, "wait", forbidden)
        assert notes.is_blocked("a")
    wake.assert_called_once_with()
    forbidden.assert_not_called()


def test_failed_closed(notes: Notes, monkeypatch: pytest.MonkeyPatch) -> None:
    from core import http_post_routing

    notes.path.unlink()
    notes.manager._refresh()
    assert notes.health_state() == "FAILED_CLOSED" and notes.is_failed_closed()
    assert notes.is_blocked("any", transport="any", effort="any")
    send, later = Mock(), Mock(side_effect=AssertionError("dispatch continued"))
    route = SimpleNamespace(
        model_id="any",
        handler=SimpleNamespace(headers={}, _send=send),
        host=SimpleNamespace(_MODEL_NOTES_FILTER=notes),
    )
    monkeypatch.setattr(http_post_routing, "_identify", lambda context: route)
    monkeypatch.setattr(http_post_routing, "_resolve_alias", later)
    assert http_post_routing.resolve_post_route(Mock()) is None
    assert send.call_args.args[0] == 503
    later.assert_not_called()


def test_alias_warning_once_stderr_only(
    notes: Notes,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    capsys.readouterr()
    monkeypatch.setattr(mod, "_alias_warned", False)
    monkeypatch.setenv("MODEL_NOTES_PATH", str(notes.path))
    monkeypatch.setenv("BRIDGE_MODEL_NOTES_PATH", "/missing/secondary")
    constructor = Mock(return_value=notes.manager)
    monkeypatch.setattr(mod, "ModelNotesSnapshotManager", constructor)
    for _ in range(3):
        assert mod.ModelNotesFilter().path == notes.path
        assert mod.validate_notes_cli() == 0
    output = capsys.readouterr()
    assert output.out == "" and len(output.err.splitlines()) == 1
    assert "MODEL_NOTES_PATH" in output.err


@pytest.mark.parametrize("text", [None, "", "invalid secret=must-not-leak", VALID])
def test_validate_sync_without_daemon(
    notes: Notes,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    text: str | None,
) -> None:
    notes.path.unlink() if text is None else notes.path.write_text(
        text, encoding="utf-8"
    )
    forbidden = Mock(side_effect=AssertionError("daemon startup or wait"))
    monkeypatch.setattr(mod, "ModelNotesSnapshotManager", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    with monkeypatch.context() as scoped:
        scoped.setattr(threading.Event, "wait", forbidden)
        assert mod.validate_notes_cli(notes.path) == (0 if text == VALID else 1)
    output = capsys.readouterr()
    assert output.out == "" and "must-not-leak" not in output.err
    forbidden.assert_not_called()


def test_cli_process_nonzero_without_daemon(notes: Notes) -> None:
    notes.path.unlink()
    result = subprocess.run(
        [sys.executable, "-m", "core.model_notes_filter"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr.strip()


def test_size_and_function_gates() -> None:
    from tests.test_transport_modularity import exceeds, functions, metrics

    for path in (Path(__file__), Path(str(mod.__file__))):
        data = path.read_bytes()
        assert len(data.splitlines()) <= 160
        assert all(not exceeds(metrics(node)) for node in functions(data).values())

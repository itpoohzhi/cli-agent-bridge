from __future__ import annotations

# Быстрые детерминированные проверки критических веток W2: гейт сессии, receipt v3, проверка receipt
# (`core/droid_session_gate.py`, `core/fleet_explain.py`, `tools/receipt_schema.py`,
# `tools/droid_receipt_verify.py`, `tools/droid_image.py`, `server.py`).

import dataclasses
import sys
import threading
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from tools import droid_image  # noqa: E402
from tools import droid_receipt_verify as verify  # noqa: E402
from tools import receipt_schema as schema  # noqa: E402
from core import droid_session_gate as gate  # noqa: E402
from core.fleet_explain import FleetExplainEntry  # noqa: E402
from test_droid_receipt_v3 import make_v3  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
from test_droid_session_gate import (  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
    ScriptedProc,
    _run,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.parametrize(
    "obj",
    [
        gate.ToolsDisablePlan("m", ()),
        FleetExplainEntry("m", "p", (), ()),
        schema.QualifiedModelSpec("m", ("a",)),
        schema.ReceiptV3((), ()),
    ],
)
def test_wave_dataclasses_are_frozen_and_slotted(obj: Any) -> None:
    first = dataclasses.fields(obj)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, first, "x")
    assert not hasattr(obj, "__dict__")


# ---- server: receipt и инициализация сессии ---------------------------------------------


def test_tools_receipt_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_load_receipt", lambda: ("", make_v3(schema=2)))
    with pytest.raises(server.RpcError, match="droid receipt invalid: schema_mismatch"):
        server._tools_receipt()
    monkeypatch.setattr(server, "_load_receipt", lambda: ("", make_v3()))
    assert isinstance(server._tools_receipt(), schema.ReceiptV3)
    monkeypatch.setattr(server, "_load_receipt", lambda: ("", None))
    assert server._tools_receipt() is None

    def unavailable() -> tuple[str, object]:
        raise server.LauncherUnavailable("gone")

    monkeypatch.setattr(server, "_load_receipt", unavailable)
    with pytest.raises(server.RpcError, match="changed during spawn"):
        server._tools_receipt()


def test_initialize_counts_only_real_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "RECEIPT_REQUIRED", False)
    run = object.__new__(server.Run)
    run.cancel, run.droid_real, run.sid = threading.Event(), -1, ""
    run.plan = {
        "settings": ("m", "high", "high"),
        "work_dir": "/w",
        "title": "t",
        "system": "",
    }
    service = {"role": "user", "content": "<system-reminder>x"}
    real = {"role": "user", "content": "hi"}
    proc = mock.Mock()
    proc.call.return_value = (
        {
            "sessionId": "s1",
            "settings": {
                "modelId": "m",
                "reasoningEffort": "high",
                "autonomyLevel": "high",
            },
            "session": {"messages": [service, real, real]},
        },
        [],
    )
    run._disable_native_tools = mock.Mock()
    run._initialize(proc)
    assert (run.sid, run.droid_real) == ("s1", 2)
    run._disable_native_tools.assert_called_once_with(proc, "m")


class NoModelProc(ScriptedProc):
    """droid, чей load_session не сообщает modelId: модель берётся из плана."""

    def call(self, method: str, params: dict[str, Any], cancel: object = None) -> Any:
        result, notes = super().call(method, params, cancel)
        if method == "droid.load_session":
            result["settings"].pop("modelId")
        return result, notes


def test_restore_without_reported_model_uses_planned_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run(monkeypatch, "deepseek-v4.1-flash", "deepseek-v4.1-flash")
    proc = NoModelProc("deepseek-v4.1-flash")
    assert run._load(proc) is True
    assert sorted(proc.disabled) == ["Read", "edit-cli"]


# ---- droid_receipt_verify ----------------------------------------------------------------


def test_droid_models_reads_overrides_then_static(tmp_path: Path) -> None:
    (tmp_path / "droid.yaml").write_text(
        "models_overrides: {m1: {}, m2: {}}\ndiscovery: {static: [m2, m3]}\n"
    )
    assert verify.droid_models(tmp_path) == ["m1", "m2", "m3"]


@pytest.mark.parametrize("text", [None, "- a\n- b\n", "a: [\n", ""])
def test_droid_models_is_fail_closed(tmp_path: Path, text: str | None) -> None:
    if text is not None:
        (tmp_path / "droid.yaml").write_text(text)
    assert verify.droid_models(tmp_path) == []


# ---- droid_image ------------------------------------------------------------------------


def test_main_reports_missing_source_and_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    missing = tmp_path / "nope"
    assert droid_image.main(["--source", str(missing)]) == 2
    assert str(missing) in capsys.readouterr().err
    assert droid_image.main([]) == 2
    assert str(tmp_path / ".local" / "bin" / "droid") in capsys.readouterr().err


def test_main_help_uses_first_docstring_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", "500")
    with pytest.raises(SystemExit):
        droid_image.main(["--help"])
    first = (droid_image.__doc__ or "").splitlines()[0]
    assert first in capsys.readouterr().out

from __future__ import annotations

# Быстрые детерминированные проверки критических веток W2: гейт сессии, receipt v3, квалификация моделей
# (`core/droid_session_gate.py`, `core/fleet_explain.py`, `tools/receipt_schema.py`,
# `tools/droid_qualify_models.py`, `tools/droid_receipt_verify.py`, `tools/droid_image.py`, `server.py`).

import dataclasses
import io
import json
import queue
import sys
import threading
from argparse import Namespace
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import droid_image  # noqa: E402
import droid_qualify_models as qualify  # noqa: E402
import droid_receipt_verify as verify  # noqa: E402
import receipt_schema as schema  # noqa: E402
import server  # noqa: E402
from core import droid_session_gate as gate  # noqa: E402
from core.fleet_explain import FleetExplainEntry  # noqa: E402
from test_droid_receipt_v3 import (  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
    QUALIFIED,
    PerModelRpc,
    make_v3,
)
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
        qualify.ProbeSettings(Path("."), "high", "auto"),
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


# ---- droid_qualify_models и droid_receipt_verify ----------------------------------------


def test_init_params_keep_settings_profile_and_effort() -> None:
    settings = qualify.ProbeSettings(Path("/w"), "high", "auto")
    assert qualify.init_params(settings, "m") == {
        "machineId": "droid-image-probe",
        "cwd": "/w",
        "modelId": "m",
        "reasoningEffort": "high",
        "autonomyLevel": "auto",
        "interactionMode": "auto",
        "title": "droid-image-probe",
        "disableBuiltinSkills": True,
        "autoRejectPermissionRequests": True,
    }


def test_qualify_model_rejects_substituted_model_and_empty_catalogue() -> None:
    settings = qualify.ProbeSettings(Path("/w"), "high", "high")
    with pytest.raises(qualify.ProbeError, match="подменил модель"):
        qualify.qualify_model(lambda: PerModelRpc({"m": ["a"]}, "m"), settings, "m")
    with pytest.raises(qualify.ProbeError, match="некорректный каталог"):
        qualify.qualify_model(lambda: PerModelRpc({"m": []}), settings, "m")
    spec = qualify.qualify_model(lambda: PerModelRpc({"m": ["b", "a"]}), settings, "m")
    assert spec == schema.QualifiedModelSpec("m", ("b", "a"))


class ClosingRpc(PerModelRpc):
    """PerModelRpc, считающий close() и роняющий выбранный метод."""

    def __init__(self, fail_on: str = "") -> None:
        super().__init__({"m": ["a"]})
        self.closed, self.fail_on = 0, fail_on

    def call(
        self, method: str, params: Mapping[str, object], timeout: float = 0.0
    ) -> droid_image.RpcExchange:
        if method == self.fail_on:
            raise qualify.ProbeError(f"boom {method}")
        return super().call(method, params, timeout)

    def close(self) -> None:
        self.closed += 1


@pytest.mark.parametrize("fail_on", ["", "droid.initialize_session", "droid.list_tools"])
def test_qualify_model_closes_session_in_every_outcome(fail_on: str) -> None:
    """T-LIFE/O-EXIT: процесс droid закрывается ровно один раз при успехе и при исключении вызова."""
    rpc = ClosingRpc(fail_on)
    settings = qualify.ProbeSettings(Path("/w"), "high", "high")
    if fail_on:
        with pytest.raises(qualify.ProbeError, match=f"boom {fail_on}"):
            qualify.qualify_model(lambda: rpc, settings, "m")
    else:
        assert qualify.qualify_model(lambda: rpc, settings, "m").tool_ids == ("a",)
    assert rpc.closed == 1


def test_qualify_models_closes_every_opened_session_before_failing() -> None:
    opened: list[ClosingRpc] = []

    def open_rpc() -> ClosingRpc:
        opened.append(ClosingRpc("droid.list_tools" if len(opened) == 1 else ""))
        return opened[-1]

    settings = qualify.ProbeSettings(Path("/w"), "high", "high")
    with pytest.raises(qualify.ProbeError, match="boom"):
        qualify.qualify_models(open_rpc, settings, ["m", "m", "m"])
    assert [r.closed for r in opened] == [1, 1]


def test_resolve_models_prefers_cli_list_else_manifest(tmp_path: Path) -> None:
    (tmp_path / "droid.yaml").write_text(
        "models_overrides: {m1: {}, m2: {}}\ndiscovery: {static: [m2, m3]}\n"
    )
    args = Namespace(models="a, b ,,", providers_dir=str(tmp_path))
    assert qualify.resolve_models(args) == ["a", "b"]
    args.models = ""
    assert qualify.resolve_models(args) == ["m1", "m2", "m3"]
    assert verify.droid_models(tmp_path) == ["m1", "m2", "m3"]


@pytest.mark.parametrize("text", [None, "- a\n- b\n", "a: [\n", ""])
def test_droid_models_is_fail_closed(tmp_path: Path, text: str | None) -> None:
    if text is not None:
        (tmp_path / "droid.yaml").write_text(text)
    assert verify.droid_models(tmp_path) == []


# ---- droid_image ------------------------------------------------------------------------


def test_install_image_probes_other_models_with_probe_effort(tmp_path: Path) -> None:
    seen: list[str] = []

    class Recording(PerModelRpc):
        def call(
            self, method: str, params: Mapping[str, object], timeout: float = 0.0
        ) -> droid_image.RpcExchange:
            if method == "droid.initialize_session":
                seen.append(str(params["reasoningEffort"]))
            return super().call(method, params, timeout)

    source = tmp_path / "droid-src"
    source.write_bytes(b"scripted-image")
    source.chmod(0o755)
    rpc = Recording({m: list(ids) for m, ids in QUALIFIED.items()})
    with mock.patch.object(droid_image, "_Rpc", lambda image, cwd, home: rpc):
        droid_image.install_image(source, tmp_path / "ws", models=["gpt-6.1-sol"])
    assert seen and set(seen) == {droid_image.PROBE_MODEL_EFFORT[1]}


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


# ---- droid_image._Rpc.call: ответ, нотификации и ошибки протокола ----------------------------


def _wire_rpc(*frames: dict[str, Any] | None) -> Any:
    """`_Rpc` без процесса: stdin - буфер, inbox заранее наполнен кадрами."""
    rpc = cast(Any, object.__new__(droid_image._Rpc))  # pyright: ignore[reportPrivateUsage]
    rpc.proc, rpc.inbox, rpc._next = mock.Mock(stdin=io.BytesIO()), queue.Queue(), 0
    for frame in frames:
        rpc.inbox.put(frame)
    return rpc


def test_rpc_call_returns_result_with_notifications_and_sends_frame() -> None:
    note = {"notification": {"type": "settings_updated"}}
    other = {"method": "droid.other", "params": {"skip": True}}
    notified = {"method": "droid.session_notification", "params": note}
    rpc = _wire_rpc(other, notified, {"id": "p1", "result": {"ok": True}})
    got = rpc.call("droid.m", {"a": 1}, timeout=1.0)
    assert got == droid_image.RpcExchange({"ok": True}, [note])
    assert (got.result, got.notifications) == ({"ok": True}, [note])
    sent = json.loads(rpc.proc.stdin.getvalue())
    assert (sent["id"], sent["method"], sent["params"]) == ("p1", "droid.m", {"a": 1})
    assert sent["factoryApiVersion"] == schema.RPC_API_VERSION


def test_rpc_call_non_dict_result_is_empty_and_errors_are_probe_errors() -> None:
    assert _wire_rpc({"id": "p1", "result": [1]}).call("m", {}, 1.0).result == {}
    with pytest.raises(droid_image.ProbeError, match="boom"):
        _wire_rpc({"id": "p1", "error": "boom"}).call("m", {}, 1.0)
    with pytest.raises(droid_image.ProbeError, match="завершился"):
        _wire_rpc(None).call("m", {}, 1.0)
    with pytest.raises(droid_image.ProbeError, match="нет ответа"):
        _wire_rpc().call("m", {}, 0.05)

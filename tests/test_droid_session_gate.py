from __future__ import annotations

# Гейт допуска модели и отключения нативных tools при ЛЮБОЙ смене модели сессии (восстановление и
# горячее продолжение): receipt v3 проверяет и исходную, и целевую модель до пользовательского сообщения.

import sys
import threading
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import receipt_schema as schema  # noqa: E402
import server  # noqa: E402
from core import droid_session_gate as gate  # noqa: E402
from test_droid_receipt_v3 import make_v3  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

CATALOGS = {
    "gpt-6.1-sol": ["Read", "apply-patch-cli"],
    "deepseek-v4.1-flash": ["Read", "edit-cli"],
    "claude-sonnet-5-5": ["Read", "edit-cli", "Grep"],
}
# Каталог живого droid шире квалифицированного receipt: `legacy-model` в receipt не входит.
LIVE_CATALOGS = {**CATALOGS, "legacy-model": ["Read"]}


def _qualified() -> schema.ReceiptV3:
    """Разбор receipt только во время теста: сбой схемы даёт FAILED, а не ошибку collection."""
    parsed = schema.ReceiptV3.parse(make_v3(CATALOGS))
    assert isinstance(parsed, schema.ReceiptV3)
    return parsed


# ---- чистый гейт -----------------------------------------------------------------------


def test_admit_model_is_fail_closed_for_unqualified_model() -> None:
    assert gate.admit_model(None, "any-model") is None
    assert gate.admit_model(_qualified(), "gpt-6.1-sol") == ("Read", "apply-patch-cli")
    with pytest.raises(gate.ToolsGateError, match="not qualified"):
        gate.admit_model(_qualified(), "not-qualified-model")


def test_plan_tools_disable_checks_catalogue_and_applies_keep() -> None:
    ids = ("Read", "apply-patch-cli")
    plan = gate.plan_tools_disable(ids, _qualified(), "gpt-6.1-sol", ("Read",))
    assert plan.disabled_ids == ("apply-patch-cli",)
    assert gate.plan_tools_disable(ids, None, "free", ()).disabled_ids == tuple(
        sorted(ids)
    )
    with pytest.raises(gate.ToolsGateError, match="differs"):
        gate.plan_tools_disable(ids, _qualified(), "deepseek-v4.1-flash", ())
    with pytest.raises(gate.ToolsGateError, match="invalid catalogue"):
        gate.plan_tools_disable((), _qualified(), "gpt-6.1-sol", ())


def test_verify_tools_disabled_requires_readback_of_every_id() -> None:
    plan = gate.ToolsDisablePlan("m", ("a", "b"))
    gate.verify_tools_disabled(plan, {"disabledToolIds": ["b", "a", "c"]})
    for bad in (None, {}, {"disabledToolIds": ["a"]}, {"disabledToolIds": "ab"}):
        with pytest.raises(gate.ToolsGateError):
            gate.verify_tools_disabled(plan, bad)


# ---- Run: смена модели загруженной/горячей сессии ---------------------------------------


class ScriptedProc:
    """Живой droid: каталог tools зависит от модели сессии; журнал всех RPC-вызовов."""

    protocol_version = "1.2.3"
    dead = overflowed = retired = busy = False

    def __init__(self, model: str) -> None:
        self.model, self.disabled = model, []
        self.log: list[tuple[str, dict[str, Any]]] = []

    def _settings(self) -> dict[str, Any]:
        return {
            "modelId": self.model,
            "reasoningEffort": "high",
            "autonomyLevel": "high",
            "disabledToolIds": self.disabled,
        }

    def call(
        self, method: str, params: dict[str, Any], cancel: object = None
    ) -> tuple[dict[str, Any], list[Any]]:
        self.log.append((method, params))
        if method == "droid.list_tools":
            return {"tools": [{"id": i} for i in LIVE_CATALOGS[self.model]]}, []
        if method == "droid.load_session":
            return {"session": {"messages": []}, "settings": self._settings()}, []
        self.model = params.get("modelId", self.model)
        self.disabled = params.get("disabledToolIds", self.disabled)
        note = {
            "notification": {"type": "settings_updated", "settings": self._settings()}
        }
        return {}, [note]

    def drain_stale(self) -> None:
        return None

    def methods(self) -> list[str]:
        return [method for method, _ in self.log]


def _run(monkeypatch: pytest.MonkeyPatch, current: str, wanted: str) -> Any:
    monkeypatch.setattr(server, "RECEIPT_REQUIRED", True)
    monkeypatch.setattr(server, "_load_receipt", lambda: ("", make_v3(CATALOGS)))
    run = object.__new__(server.Run)
    run.cancel = threading.Event()
    run.sid, run.droid_real, run.path = "", 0, "restore"
    run.plan = {
        "settings": (wanted, "high", "high"),
        "current_settings": (current, "high", "high"),
        "sid": "sid-1",
        "hash8": "h8",
        "droid_real": -1,
        "send": [{"role": "user", "text": "hi"}],
        "all_items": [],
    }
    run._send_items = mock.Mock(return_value=True)
    run._consume = mock.Mock()
    return run


@pytest.mark.parametrize("path", ["restore", "hot"])
def test_unqualified_target_model_is_rejected_before_any_message(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    run = _run(monkeypatch, "gpt-6.1-sol", "not-qualified-model")
    proc = ScriptedProc("gpt-6.1-sol")
    run.path, run.proc = path, proc
    with pytest.raises(gate.ToolsGateError, match="not qualified"):
        run._run_turn() if path == "hot" else run._load(proc)
    assert (
        proc.model == "gpt-6.1-sol"
    )  # сессия не переключена на неквалифицированную модель
    assert not [p for m, p in proc.log if "modelId" in p]
    run._send_items.assert_not_called()


def _assert_new_model_tools_disabled(proc: ScriptedProc) -> None:
    """Read-back подтвердил набор ИМЕННО новой модели (edit-cli), а не прежний apply-patch-cli."""
    assert proc.model == "deepseek-v4.1-flash"
    assert sorted(proc.disabled) == ["Read", "edit-cli"]
    methods = proc.methods()
    switch = methods.index("droid.update_session_settings")
    assert methods.index("droid.list_tools", switch) > switch


@pytest.mark.parametrize("path", ["restore", "hot"])
def test_model_switch_redisables_native_tools_of_the_new_model(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    run = _run(monkeypatch, "gpt-6.1-sol", "deepseek-v4.1-flash")
    proc = ScriptedProc("gpt-6.1-sol")
    run.path, run.proc = path, proc
    if path == "hot":
        run._run_turn()
        run._send_items.assert_called_once()  # сообщение уходит только после отключения
    else:
        assert run._load(proc) is True
    _assert_new_model_tools_disabled(proc)


def test_same_model_effort_change_does_not_redisable_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run(monkeypatch, "gpt-6.1-sol", "gpt-6.1-sol")
    run.plan["current_settings"] = ("gpt-6.1-sol", "low", "high")
    proc = ScriptedProc("gpt-6.1-sol")
    run._sync_settings(proc, run.plan["settings"])
    assert proc.methods() == ["droid.update_session_settings"]


def test_loaded_session_of_unqualified_current_model_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run(monkeypatch, "legacy-model", "gpt-6.1-sol")
    proc = ScriptedProc("legacy-model")
    with pytest.raises(gate.ToolsGateError, match="not qualified"):
        run._load(proc)
    assert not [p for m, p in proc.log if "disabledToolIds" in p]

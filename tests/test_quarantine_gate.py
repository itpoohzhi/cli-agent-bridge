"""L1-тесты карантинного ролевого гейта (QT-2, QT-7, QT-10)."""

from __future__ import annotations

import json

import pytest

from core import quarantine_gate as qg

GATED_ROLES = ["coder", "reviewer", "judge", "answer-review", "council"]
OPEN_ROLES = ["worker", "explorer", "adhoc", "probe"]
UNCONFIRMED = ["quarantine", "quarantine_failed", "stale", "probing"]


def _sidecar(status: str) -> qg.SidecarView:
    return qg.SidecarView.from_dict(
        {
            "schema": "catalog-lock/1",
            "models": {"m-x": {"status": status, "family": "F"}},
        }
    )


@pytest.mark.parametrize("status", UNCONFIRMED)
@pytest.mark.parametrize("role", GATED_ROLES)
def test_unconfirmed_denied_for_gated_roles(role: str, status: str) -> None:
    decision = qg.gate("m-x", role + "-123", _sidecar(status), qg.RoleClasses())
    assert isinstance(decision, qg.Deny)
    assert decision.reason == "model_quarantined"
    assert decision.http == 403
    assert decision.status == status


@pytest.mark.parametrize("status", UNCONFIRMED)
@pytest.mark.parametrize("role", OPEN_ROLES)
def test_unconfirmed_allowed_for_open_roles(role: str, status: str) -> None:
    decision = qg.gate("m-x", role + "-1", _sidecar(status), qg.RoleClasses())
    assert isinstance(decision, qg.Allow)


@pytest.mark.parametrize("role", GATED_ROLES + OPEN_ROLES + ["unknown-role"])
def test_confirmed_allowed_everywhere(role: str) -> None:
    assert isinstance(
        qg.gate("m-x", role + "-1", _sidecar("confirmed"), qg.RoleClasses()), qg.Allow
    )


def test_unknown_role_is_gated_default_deny() -> None:
    classes = qg.RoleClasses()
    assert classes.class_of("totally-new") == qg.CLASS_GATED
    assert isinstance(
        qg.gate("m-x", "totally-new-1", _sidecar("quarantine"), classes), qg.Deny
    )


def test_missing_header_is_adhoc() -> None:
    assert qg.role_from_subagent_id(None) == "adhoc"
    assert qg.role_from_subagent_id("") == "adhoc"
    assert qg.role_from_subagent_id("   ") == "adhoc"
    assert qg.role_from_subagent_id("-weird") == "adhoc"
    assert qg.role_from_subagent_id("coder-abc-def") == "coder"
    assert isinstance(
        qg.gate("m-x", None, _sidecar("quarantine"), qg.RoleClasses()), qg.Allow
    )
    assert isinstance(
        qg.gate("m-x", "", _sidecar("quarantine"), qg.RoleClasses()), qg.Allow
    )


def test_absent_model_allowed_legacy() -> None:
    decision = qg.gate("not-there", "coder-1", _sidecar("quarantine"), qg.RoleClasses())
    assert isinstance(decision, qg.Allow)
    assert isinstance(
        qg.gate("x", "coder-1", qg.SidecarView(), qg.RoleClasses()), qg.Allow
    )


def test_disabled_and_rejected_denied_even_for_open() -> None:
    for status in ("disabled", "rejected", "weird"):
        assert isinstance(
            qg.gate("m-x", "worker-1", _sidecar(status), qg.RoleClasses()), qg.Deny
        )


def test_deny_body_shape() -> None:
    assert qg.deny_body("m-x", "quarantine") == {
        "error": {"type": "model_quarantined", "model": "m-x", "status": "quarantine"}
    }
    deny = qg.gate("m-x", "judge-1", _sidecar("stale"), qg.RoleClasses())
    assert isinstance(deny, qg.Deny)
    assert deny.body() == qg.deny_body("m-x", "stale")


def test_role_classes_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        qg.ENV_ROLE_CLASSES, json.dumps({"open": ["coder"], "quorum": ["judge"]})
    )
    classes = qg.RoleClasses.from_env()
    assert classes.class_of("coder") == qg.CLASS_OPEN
    assert classes.class_of("worker") == qg.CLASS_GATED
    assert isinstance(
        qg.gate("m-x", "coder-1", _sidecar("quarantine"), classes), qg.Allow
    )
    assert isinstance(qg.gate("m-x", "worker-1", _sidecar("quarantine")), qg.Deny)
    monkeypatch.setenv(qg.ENV_ROLE_CLASSES, "not-json")
    assert qg.RoleClasses.from_env() == qg.RoleClasses()


def test_sidecar_from_path(tmp_path) -> None:
    path = tmp_path / "catalog.lock.json"
    assert qg.SidecarView.from_path(path).models == {}
    path.write_text(
        json.dumps({"models": {"a": {"status": "stale"}}}), encoding="utf-8"
    )
    view = qg.SidecarView.from_path(path)
    assert view.status_of("a") == "stale"
    assert view.status_of("b") is None
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        qg.SidecarView.from_path(path)


# --- Подключение гейта к обработчику запросов server.py (F-001) -------------------------

import http.client  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

import server  # noqa: E402
from bridge_testlib import BridgeCase, chat_body  # noqa: E402

STAND_MODEL = "claude-sonnet-5-5"
FLAG = "BRIDGE_QUARANTINE_GATE_ENABLED"


def _write_sidecar(path: Path, status: str, model: str = STAND_MODEL) -> None:
    path.write_text(
        json.dumps({"schema": "catalog-lock/1", "models": {model: {"status": status}}}),
        encoding="utf-8",
    )


@pytest.mark.parametrize("role", GATED_ROLES)
def test_server_denial_gated_role_quarantined(
    role: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "catalog.lock.json"
    _write_sidecar(lock, "quarantine")
    monkeypatch.setenv(FLAG, "true")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "none.json"))
    monkeypatch.setenv("BRIDGE_CATALOG_LOCK", str(lock))
    denial = server._quarantine_denial(STAND_MODEL, role + "-1")
    assert isinstance(denial, qg.Deny)
    assert denial.http == 403
    assert denial.body() == qg.deny_body(STAND_MODEL, "quarantine")


@pytest.mark.parametrize("role", OPEN_ROLES)
def test_server_allows_open_role_and_confirmed(
    role: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "catalog.lock.json"
    monkeypatch.setenv(FLAG, "true")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "none.json"))
    monkeypatch.setenv("BRIDGE_CATALOG_LOCK", str(lock))
    _write_sidecar(lock, "quarantine")
    assert server._quarantine_denial(STAND_MODEL, role + "-1") is None
    _write_sidecar(lock, "confirmed")
    assert server._quarantine_denial(STAND_MODEL, "coder-1") is None


def test_server_gate_off_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "catalog.lock.json"
    _write_sidecar(lock, "quarantine")
    monkeypatch.delenv(FLAG, raising=False)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "none.json"))
    monkeypatch.setenv("BRIDGE_CATALOG_LOCK", str(lock))
    assert server._quarantine_denial(STAND_MODEL, "coder-1") is None


def test_server_unreadable_sidecar_fails_closed_for_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "catalog.lock.json"
    lock.write_text("not-json", encoding="utf-8")
    monkeypatch.setenv(FLAG, "true")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "none.json"))
    monkeypatch.setenv("BRIDGE_CATALOG_LOCK", str(lock))
    assert isinstance(server._quarantine_denial(STAND_MODEL, "coder-1"), qg.Deny)
    assert server._quarantine_denial(STAND_MODEL, "worker-1") is None


class QuarantineGateHttpTests(BridgeCase):
    """Сквозной HTTP: гейт срабатывает в `Handler.do_POST` до обработки запроса."""

    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.lock = Path(self._tmp.name) / "catalog.lock.json"
        os.environ[FLAG] = "true"
        os.environ["BRIDGE_DYNAMIC_CONFIG_PATH"] = str(Path(self._tmp.name) / "none.json")
        os.environ["BRIDGE_CATALOG_LOCK"] = str(self.lock)

    def _post_as(self, subagent_id: str | None):
        headers = {
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        }
        if subagent_id is not None:
            headers["X-Subagent-Id"] = subagent_id
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                body=json.dumps(chat_body(STAND_MODEL)),
                headers=headers,
            )
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
        finally:
            conn.close()

    def test_quarantined_model_rejected_for_coder_403(self) -> None:
        _write_sidecar(self.lock, "quarantine")
        status, body = self._post_as("coder-1")
        self.assertEqual(status, 403)
        self.assertEqual(body, qg.deny_body(STAND_MODEL, "quarantine"))

    def test_quarantined_model_allowed_for_worker(self) -> None:
        _write_sidecar(self.lock, "quarantine")
        status, _ = self._post_as("worker-1")
        self.assertEqual(status, 200)

    def test_confirmed_model_allowed_for_coder(self) -> None:
        _write_sidecar(self.lock, "confirmed")
        status, _ = self._post_as("coder-1")
        self.assertEqual(status, 200)

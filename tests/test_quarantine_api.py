from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import core.model_penalty as penalty_module
from core.model_penalty import ModelPenaltyTracker
from tests.quarantine_api_support import load_quarantine_methods


@pytest.fixture
def clock(monkeypatch):
    current = [1_700_000_000.0]
    monkeypatch.setattr(penalty_module.time, "time", lambda: current[0])
    return current


@pytest.fixture
def tracker(tmp_path, clock):
    return ModelPenaltyTracker(
        storage_path=tmp_path / "penalties.json",
        max_start_fails=3,
        cooldown_seconds=10.0,
    )


def test_initial_payload(tracker):
    assert tracker.configured_max_start_fails == 3
    assert tracker.max_start_fails == 3
    assert tracker.enabled is True
    assert tracker.get_quarantine_payload(["a", "b"]) == {
        "enabled": True,
        "max_start_fails": 3,
        "cooldown_seconds": 10.0,
        "penalized_count": 0,
        "penalized_models": [],
        "available_models": ["a", "b"],
    }


def test_toggle_persists_and_reloads_across_instances(tracker):
    assert tracker.set_enabled(False) is False
    assert tracker.max_start_fails == 999999999

    raw = json.loads(tracker.storage_path.read_text())
    assert raw["_meta"] == {
        "quarantine_enabled": False,
        "configured_max_start_fails": 3,
    }

    other = ModelPenaltyTracker(
        tracker.storage_path, max_start_fails=7, cooldown_seconds=10
    )
    assert other.enabled is False
    assert other.configured_max_start_fails == 3
    assert other.max_start_fails == 999999999
    assert other.get_all_penalties() == {}

    assert other.set_enabled(True) is True
    assert other.max_start_fails == 3

    assert tracker.get_quarantine_payload()["enabled"] is True
    assert tracker.max_start_fails == 3


def test_manual_penalty_normalization_and_expiration(tracker, clock):
    status = tracker.manually_penalize("  MODEL-A  ", 30)
    assert status == {
        "model": "model-a",
        "fails": 1,
        "is_penalized": True,
        "remaining_cooldown": 30,
        "penalized_until": clock[0] + 30,
        "last_fail_at": clock[0],
        "last_error": "manually penalized by user",
    }
    assert tracker.is_penalized("MODEL-A") == (True, 30)

    payload = tracker.get_quarantine_payload()
    assert payload["penalized_count"] == 1
    assert payload["penalized_models"] == [status]

    clock[0] += 30
    assert tracker.get_quarantine_payload()["penalized_count"] == 0
    assert tracker.is_penalized("model-a") == (False, 0)
    persisted = json.loads(tracker.storage_path.read_text())
    assert persisted["model-a"]["fails"] == 0
    assert persisted["model-a"]["penalized_until"] == 0


def test_disabled_quarantine_preserves_existing_penalties(tracker):
    tracker.manually_penalize("a", 60)
    tracker.set_enabled(False)

    assert tracker.is_penalized("a") == (False, 0)
    payload = tracker.get_quarantine_payload()
    assert payload["enabled"] is False
    assert payload["penalized_count"] == 1

    tracker.set_enabled(True)
    assert tracker.is_penalized("a") == (True, 60)


def test_disabled_threshold_does_not_trigger_normal_failures(tracker):
    tracker.set_enabled(False)
    for _ in range(4):
        penalized, _, until = tracker.record_start_failure("a", "startup error")
        assert penalized is False
        assert until == 0


def test_unban_resets_failure_and_escalation(tracker):
    for _ in range(3):
        tracker.record_start_failure("a", "startup error")
    tracker.unpenalize_model("A")

    status = tracker.get_model_status("a")
    assert status["fails"] == 0
    assert status["penalized_until"] == 0
    assert status["last_error"] is None
    raw = json.loads(tracker.storage_path.read_text())
    assert raw["a"]["penalty_trips"] == 0

    tracker.unpenalize_model("missing")
    assert "missing" not in tracker.get_all_penalties()


def test_clear_all_preserves_configuration_and_hides_meta(tracker):
    tracker.manually_penalize("a")
    tracker.set_enabled(False)
    tracker.reset_all()

    assert tracker.get_all_penalties() == {}
    payload = tracker.get_quarantine_payload()
    assert payload["enabled"] is False
    assert payload["penalized_models"] == []

    assert json.loads(tracker.storage_path.read_text()) == {
        "_meta": {
            "quarantine_enabled": False,
            "configured_max_start_fails": 3,
        }
    }


def test_legacy_document_without_metadata(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "MODEL-A": {
                    "fails": 1,
                    "penalized_until": 0,
                    "last_fail_at": 123,
                    "last_error": "startup failed",
                }
            }
        )
    )
    tracker = ModelPenaltyTracker(path, max_start_fails=4)
    assert tracker.enabled is True
    assert tracker.max_start_fails == 4
    assert tracker.get_all_penalties()["model-a"]["fails"] == 1


@pytest.mark.parametrize(
    "meta",
    [
        {},
        {"quarantine_enabled": "false", "configured_max_start_fails": True},
        {"quarantine_enabled": None, "configured_max_start_fails": 0},
        {"configured_max_start_fails": "8"},
    ],
)
def test_invalid_metadata_uses_defaults(tmp_path, meta):
    path = tmp_path / "penalties.json"
    path.write_text(json.dumps({"_meta": meta}))
    tracker = ModelPenaltyTracker(path, max_start_fails=4)
    assert tracker.enabled is True
    assert tracker.configured_max_start_fails == 4
    assert tracker.max_start_fails == 4
    assert tracker.get_all_penalties() == {}


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan"), True])
def test_invalid_manual_duration_does_not_mutate(tracker, duration):
    with pytest.raises(ValueError):
        tracker.manually_penalize("a", duration)
    assert tracker.get_all_penalties() == {}


def test_reserved_model_id_cannot_overwrite_metadata(tracker):
    with pytest.raises(ValueError):
        tracker.manually_penalize(" _META ")
    assert tracker.get_all_penalties() == {}


def test_infrastructure_errors_are_not_counted(tracker):
    assert tracker.record_start_failure("a", "http_502 bad gateway") == (False, 0, 0)


def test_active_cooldown_is_not_extended(tracker, clock):
    tracker.manually_penalize("a", 30)
    before = tracker.storage_path.read_bytes()
    clock[0] += 5
    assert tracker.record_start_failure("a", "startup error") == (
        True,
        1,
        clock[0] + 25,
    )
    assert tracker.storage_path.read_bytes() == before


def test_quarantine_accepts_adapter_model_tuples(tracker):
    tuples = [
        (SimpleNamespace(name="adapter-a"), SimpleNamespace(id="model-a")),
        (SimpleNamespace(name="adapter-b"), SimpleNamespace(id="model-b")),
    ]
    backends = SimpleNamespace(models=lambda: tuples)
    ns = {
        "json": json,
        "_PENALTY_TRACKER": tracker,
        "_auth_ok": lambda handler: True,
        "BACKENDS": backends,
    }
    sent = []
    handler = SimpleNamespace(
        path="/v1/quarantine",
        _send=lambda status, payload: sent.append((status, payload)),
    )
    load_quarantine_methods(ns)["do_GET"](handler)
    status, body = sent[0]
    assert status == 200
    assert body["available_models"] == ["model-a", "model-b"]

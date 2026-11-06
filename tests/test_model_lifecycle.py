"""Тесты жизненного цикла модели (core/model_lifecycle.py)."""

from __future__ import annotations

import dataclasses
import os

import pytest

from core import model_lifecycle as ml
from core.model_lifecycle import (
    EVENTS,
    STATUSES,
    LifecycleConfig,
    LifecycleError,
    LifecycleRegistry,
    ModelRecord,
    transition,
)

NOW = 1_000_000.0
CFG = LifecycleConfig(
    retry_backoff_s=(300.0, 1800.0, 7200.0),
    rate_limited_backoff_s=900.0,
    miss_limit=3,
    history_max=20,
)
PASS = {"receipt_sha256": "a" * 64, "efforts_proven": ("low", "high")}


def rec(status: str, **kw) -> ModelRecord:
    return ModelRecord("p", "m", "f" * 64, status, **kw)


# (status, event, payload, expected status)
LEGAL = [
    ("discovered", "discovered_ok", None, "quarantine"),
    ("discovered", "invalid_record", {"reason": "bad"}, "rejected"),
    ("quarantine", "probe_start", None, "probing"),
    ("stale", "probe_start", None, "probing"),
    ("quarantine_failed", "probe_start", {"force": True}, "probing"),
    ("quarantine_failed", "force", None, "probing"),
    ("probing", "probe_pass", PASS, "confirmed"),
    ("probing", "probe_fail", {"reason": "P3"}, "quarantine_failed"),
    ("probing", "probe_inconclusive", {"rate_limited": True}, "quarantine"),
    ("confirmed", "fingerprint_changed", None, "stale"),
    ("confirmed", "missing", None, "confirmed"),
    ("quarantine", "missing", None, "quarantine"),
    ("disabled", "seen", None, "discovered"),
    ("rejected", "manifest_changed", None, "discovered"),
] + [(s, "seen", None, s) for s in STATUSES if s not in ("rejected", "disabled")]


@pytest.mark.parametrize("status,event,payload,expected", LEGAL)
def test_legal_transitions(status, event, payload, expected):
    before = rec(status)
    after = transition(before, event, now=NOW, payload=payload, config=CFG)
    assert after.status == expected
    assert before.status == status  # исходная запись не изменилась
    if expected != status:
        assert after.history[-1]["from"] == status
        assert after.history[-1]["to"] == expected
        assert after.history[-1]["event"] == event
    else:
        assert after.history == ()


def _illegal_pairs():
    legal = {(s, e) for s, e, _, _ in LEGAL}
    return [(s, e) for s in STATUSES for e in EVENTS if (s, e) not in legal]


@pytest.mark.parametrize("status,event", _illegal_pairs())
def test_illegal_transitions_raise_and_leave_record(status, event):
    before = rec(status, miss_count=1, failures=2)
    snapshot = dataclasses.replace(before)
    with pytest.raises(LifecycleError):
        transition(before, event, now=NOW, payload=PASS, config=CFG)
    assert before == snapshot


def test_lifecycle_error_is_value_error():
    assert issubclass(LifecycleError, ValueError)


def test_table_matches_legal_set():
    assert set(ml.TRANSITIONS) == {(s, e) for s, e, _, _ in LEGAL}


def test_status_groups():
    assert set(ml.QUARANTINE_LIKE) == {
        "quarantine",
        "probing",
        "quarantine_failed",
        "stale",
    }
    assert set(ml.IN_CATALOG) == set(ml.QUARANTINE_LIKE) | {"confirmed"}
    assert set(ml.OPEN_ROLE_STATUSES) == set(ml.IN_CATALOG)
    assert len(STATUSES) == 8


def test_probe_pass_requires_receipt_and_efforts():
    r = rec("probing")
    for payload in (None, {}, {"receipt_sha256": "a"}, {"efforts_proven": ["low"]}):
        with pytest.raises(LifecycleError):
            transition(r, "probe_pass", now=NOW, payload=payload, config=CFG)
    ok = transition(r, "probe_pass", now=NOW, payload=PASS, config=CFG)
    assert ok.receipt_sha256 == "a" * 64
    assert ok.efforts_proven == ("low", "high")
    assert ok.failures == 0 and ok.retry_after == 0.0


def test_fingerprint_change_makes_confirmed_stale_then_probing():
    r = rec("confirmed", receipt_sha256="x", efforts_proven=("low",))
    s = transition(r, "fingerprint_changed", now=NOW, config=CFG)
    assert s.status == "stale"
    assert transition(s, "probe_start", now=NOW, config=CFG).status == "probing"


def test_inconclusive_goes_to_quarantine_with_backoff():
    r = rec("probing")
    a = transition(
        r, "probe_inconclusive", now=NOW, payload={"rate_limited": True}, config=CFG
    )
    assert a.status == "quarantine"
    assert a.retry_after == NOW + 900.0
    assert a.failures == 0
    b = transition(r, "probe_inconclusive", now=NOW, config=CFG)
    assert b.status == "quarantine"
    assert b.retry_after == NOW + 300.0


def test_deterministic_fail_backoff_grows_and_caps():
    r = rec("probing")
    delays = []
    for _ in range(5):
        failed = transition(r, "probe_fail", now=NOW, config=CFG)
        assert failed.status == "quarantine_failed"
        delays.append(failed.retry_after - NOW)
        r = transition(failed, "force", now=NOW, config=CFG)
    assert delays == [300.0, 1800.0, 7200.0, 7200.0, 7200.0]
    assert r.failures == 5


def test_probe_start_from_failed_respects_retry_after():
    failed = transition(rec("probing"), "probe_fail", now=NOW, config=CFG)
    with pytest.raises(LifecycleError):
        transition(failed, "probe_start", now=NOW + 10, config=CFG)
    ok = transition(failed, "probe_start", now=NOW + 300, config=CFG)
    assert ok.status == "probing"
    forced = transition(failed, "force", now=NOW + 1, config=CFG)
    assert forced.status == "probing"


def test_miss_limit_disables_and_seen_resets():
    r = rec("confirmed")
    r = transition(r, "missing", now=NOW, config=CFG)
    r = transition(r, "missing", now=NOW, config=CFG)
    assert r.status == "confirmed" and r.miss_count == 2
    reset = transition(r, "seen", now=NOW, config=CFG)
    assert reset.miss_count == 0 and reset.status == "confirmed"
    for _ in range(3):
        r = transition(r, "missing", now=NOW, config=CFG)
        if r.status == "disabled":
            break
    assert r.status == "disabled"
    assert r.history[-1]["to"] == "disabled"
    back = transition(r, "seen", now=NOW, config=CFG)
    assert back.status == "discovered" and back.miss_count == 0


def test_miss_limit_from_config():
    cfg = LifecycleConfig(miss_limit=1)
    r = transition(rec("quarantine"), "missing", now=NOW, config=cfg)
    assert r.status == "disabled"


def test_history_cap():
    cfg = LifecycleConfig(history_max=3)
    r = rec("discovered")
    for _ in range(5):
        r = transition(r, "discovered_ok", now=NOW, config=cfg)
        r = transition(r, "probe_start", now=NOW, config=cfg)
        r = transition(r, "probe_inconclusive", now=NOW, config=cfg)
        r = dataclasses.replace(r, status="discovered")
    assert len(r.history) == 3


def test_transition_does_not_mutate_input_history():
    r = rec("discovered")
    r2 = transition(r, "discovered_ok", now=NOW, config=CFG)
    assert r.history == () and len(r2.history) == 1


# ------------------------------ registry ---------------------------------- #


def test_registry_current_status_uses_current_fingerprint():
    reg = LifecycleRegistry(config=CFG)
    k_old = ("p", "m", "old")
    k_new = ("p", "m", "new")
    reg.register(*k_old)
    reg.register(*k_new)
    reg.apply(k_old, "discovered_ok", NOW)
    reg.apply(k_old, "probe_start", NOW)
    reg.apply(k_old, "probe_pass", NOW, PASS)
    assert reg.current_status("p", "m", "old") == "confirmed"
    assert reg.current_status("p", "m", "new") == "discovered"
    assert reg.current_status("p", "m", "other") is None
    assert reg.current_status("p", "zzz", "old") is None


def test_registry_apply_unknown_and_illegal():
    reg = LifecycleRegistry(config=CFG)
    with pytest.raises(LifecycleError):
        reg.apply(("p", "m", "f"), "discovered_ok", NOW)
    reg.register("p", "m", "f")
    with pytest.raises(LifecycleError):
        reg.apply(("p", "m", "f"), "probe_pass", NOW, PASS)
    assert reg.get(("p", "m", "f")).status == "discovered"


def test_registry_register_idempotent():
    reg = LifecycleRegistry(config=CFG)
    a = reg.register("p", "m", "f")
    reg.apply(("p", "m", "f"), "discovered_ok", NOW)
    b = reg.register("p", "m", "f")
    assert a is not b and b.status == "quarantine" and len(reg) == 1


def _populated() -> LifecycleRegistry:
    reg = LifecycleRegistry(config=CFG)
    for m in ("b", "a"):
        reg.register("p", m, "fp")
        reg.apply(("p", m, "fp"), "discovered_ok", NOW)
    reg.apply(("p", "a", "fp"), "probe_start", NOW)
    reg.apply(("p", "a", "fp"), "probe_pass", NOW, PASS)
    reg.apply(("p", "b", "fp"), "probe_start", NOW)
    reg.apply(("p", "b", "fp"), "probe_fail", NOW, {"reason": "P1"})
    return reg


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "state" / "lifecycle.json"
    reg = _populated()
    reg.save(path)
    loaded = LifecycleRegistry.load(path, config=CFG)
    assert loaded.records() == reg.records()
    a = loaded.get(("p", "a", "fp"))
    assert a.status == "confirmed" and a.efforts_proven == ("low", "high")
    b = loaded.get(("p", "b", "fp"))
    assert b.status == "quarantine_failed" and b.failures == 1 and b.reason == "P1"


def test_save_is_canonical_and_deterministic(tmp_path):
    reg = _populated()
    p1, p2 = tmp_path / "1.json", tmp_path / "2.json"
    reg.save(p1)
    LifecycleRegistry.load(p1).save(p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_atomic_persist_leaves_no_tmp(tmp_path):
    path = tmp_path / "lifecycle.json"
    reg = _populated()
    reg.save(path)
    reg.save(path)
    names = sorted(os.listdir(tmp_path))
    assert "lifecycle.json" in names
    assert not [n for n in names if ".tmp" in n]


def test_failed_save_keeps_previous_and_cleans_tmp(tmp_path, monkeypatch):
    path = tmp_path / "lifecycle.json"
    _populated().save(path)
    original = path.read_bytes()

    def boom(*a, **k):
        raise OSError("replace failed")

    monkeypatch.setattr(ml.os, "replace", boom)
    with pytest.raises(OSError):
        LifecycleRegistry(config=CFG).save(path)
    monkeypatch.undo()
    assert path.read_bytes() == original
    assert not [n for n in os.listdir(tmp_path) if ".tmp" in n]


def test_missing_file_gives_empty_registry(tmp_path):
    reg = LifecycleRegistry.load(tmp_path / "nope.json")
    assert len(reg) == 0 and reg.records() == []


@pytest.mark.parametrize(
    "text",
    [
        "{not json",
        "[]",
        '{"schema": "other/1", "records": []}',
        '{"schema": "model-lifecycle/1", "records": {}}',
        '{"schema": "model-lifecycle/1", "records": [1]}',
        '{"schema": "model-lifecycle/1", "records": [{"provider_id": "p"}]}',
        '{"schema": "model-lifecycle/1", "records": [{"provider_id": "p",'
        ' "model_id": "m", "fingerprint_sha256": "f", "status": "bogus"}]}',
    ],
)
def test_corrupt_file_raises(tmp_path, text):
    path = tmp_path / "lifecycle.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(LifecycleError):
        LifecycleRegistry.load(path)


# -------------------------------- config ---------------------------------- #


def test_config_defaults():
    cfg = LifecycleConfig.from_env({})
    assert cfg.retry_backoff_s == (300.0, 1800.0, 7200.0)
    assert cfg.rate_limited_backoff_s == 900.0
    assert cfg.miss_limit == 3
    assert cfg.history_max == 20


def test_config_from_env():
    cfg = LifecycleConfig.from_env(
        {
            "BRIDGE_PROBE_RETRY_BACKOFF_S": "1, 2.5 ,10",
            "BRIDGE_PROBE_RATE_LIMITED_BACKOFF_S": "42",
            "BRIDGE_DISCOVERY_MISS_LIMIT": "5",
            "BRIDGE_CATALOG_HISTORY_MAX": "7",
        }
    )
    assert cfg.retry_backoff_s == (1.0, 2.5, 10.0)
    assert cfg.rate_limited_backoff_s == 42.0
    assert cfg.miss_limit == 5
    assert cfg.history_max == 7


@pytest.mark.parametrize(
    "env",
    [
        {"BRIDGE_PROBE_RETRY_BACKOFF_S": "a,b"},
        {"BRIDGE_PROBE_RETRY_BACKOFF_S": "-1"},
        {"BRIDGE_PROBE_RETRY_BACKOFF_S": " , "},
        {"BRIDGE_PROBE_RATE_LIMITED_BACKOFF_S": "x"},
        {"BRIDGE_DISCOVERY_MISS_LIMIT": "0"},
        {"BRIDGE_CATALOG_HISTORY_MAX": "abc"},
    ],
)
def test_config_invalid_values_fall_back(env):
    assert LifecycleConfig.from_env(env) == LifecycleConfig.from_env({})


def test_config_reads_os_environ(monkeypatch):
    monkeypatch.setenv("BRIDGE_DISCOVERY_MISS_LIMIT", "9")
    assert LifecycleConfig.from_env().miss_limit == 9

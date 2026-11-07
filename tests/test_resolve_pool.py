"""L1-тесты детерминированного резолвера пулов (resolve_pool)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location(
    "resolve_pool_under_test", REPO / "scripts" / "resolve_pool.py"
)
assert _spec is not None and _spec.loader is not None
rp = importlib.util.module_from_spec(_spec)
sys.modules["resolve_pool_under_test"] = rp
_spec.loader.exec_module(rp)

FP = "f" * 64


def _model(
    family: str,
    quota: str,
    status: str = "confirmed",
    provider: str = "prov",
    efforts: Optional[list] = None,
    receipt: Optional[str] = None,
    fp: str = FP,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "provider": provider,
        "status": status,
        "family": family,
        "quorum_eligible": status == "confirmed" and bool(family),
        "quota_group": quota,
        "efforts_proven": efforts if efforts is not None else ["low", "high"],
    }
    if receipt is not None:
        entry["probe"] = {"receipt_sha256": receipt, "fingerprint_sha256": fp}
    return entry


def _catalog(models: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "catalog-lock/1",
        "providers": {"prov": {"fingerprint_sha256": FP}},
        "models": models,
    }


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in (
        rp.ENV_CATALOG_LOCK,
        rp.ENV_PROBE_DIR,
        rp.ENV_MAX_CANDIDATES,
        rp.ENV_TEMP_OFF,
        rp.ENV_DENIED,
        rp.ENV_DENIED_SUFFIXES,
        rp.ENV_EFFORT_ORDER,
        "POL_ROLE_CLASSES",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(rp.ENV_STATE_DIR, str(tmp_path / "state"))


FOUR = _catalog(
    {
        "m-a": _model("FamOne", "q1"),
        "m-b": _model("FamOne", "q2"),
        "m-c": _model("FamTwo", "q3"),
        "m-d": _model("FamThree", "q4"),
    }
)


def test_four_candidates_two_same_family_gives_three_distinct_families() -> None:
    lock = rp.resolve_pool("judge", 3, catalog=FOUR, seed="s")
    assert len(lock.primary) == 3
    assert len({s.family for s in lock.primary}) == 3
    assert all(not s.reserve for s in lock.primary)
    assert len(lock.reserves) == 1 and lock.reserves[0].reserve


def test_same_quota_group_never_together() -> None:
    cat = _catalog(
        {
            "m-1": _model("F1", "shared"),
            "m-2": _model("F2", "shared"),
            "m-3": _model("F3", "q3"),
            "m-4": _model("F4", "q4"),
        }
    )
    for i in range(30):
        lock = rp.resolve_pool("judge", 3, catalog=cat, seed="seed%d" % i)
        groups = [s.quota_group for s in lock.primary]
        assert len(set(groups)) == 3


def test_next_candidate_on_429_never_picks_same_quota_group() -> None:
    cat = _catalog(
        {
            "m-1": _model("F1", "q1"),
            "m-2": _model("F2", "q2"),
            "m-3": _model("F3", "q1"),
            "m-4": _model("F4", "q4"),
            "m-5": _model("F5", "q2"),
        }
    )
    checked = 0
    for i in range(30):
        lock = rp.resolve_pool("judge", 2, catalog=cat, seed="x%d" % i)
        failed = lock.primary[0]
        chosen, receipt = rp.next_candidate(
            lock, failed, "rate_limited_429", list(lock.primary)
        )
        assert "requested=%s" % failed.model in receipt["chain"]
        assert "error=rate_limited_429" in receipt["chain"]
        if chosen is not None:
            checked += 1
            assert chosen.quota_group != failed.quota_group
            assert chosen.quota_group != lock.primary[1].quota_group
            assert chosen.family != lock.primary[1].family
            assert chosen.model in receipt["chain"]
    assert checked > 0


def test_next_candidate_returns_none_when_all_reserves_blocked() -> None:
    cat = _catalog(
        {
            "m-1": _model("F1", "q1"),
            "m-2": _model("F2", "q2"),
            "m-3": _model("F3", "q1"),
        }
    )
    # при любом seed в резерве остаётся модель, делящая quota_group с одним из primary
    lock = rp.resolve_pool("judge", 2, catalog=cat, seed="z")
    failed = lock.primary[0]
    chosen, receipt = rp.next_candidate(
        lock, failed, "quota_exhausted", list(lock.primary)
    )
    assert chosen is None
    assert receipt["chain"].endswith("selected=none")
    assert receipt["selected"] is None


def test_insufficient_families_raises_quorum_unavailable() -> None:
    cat = _catalog(
        {
            "m-1": _model("F1", "q1"),
            "m-2": _model("F1", "q2"),
            "m-3": _model("F2", "q3"),
        }
    )
    with pytest.raises(rp.QuorumUnavailable) as err:
        rp.resolve_pool("judge", 3, catalog=cat, seed="s")
    assert err.value.reason == "insufficient_distinct_families"
    assert set(err.value.considered) == {"m-1", "m-2", "m-3"}


def test_insufficient_candidates() -> None:
    cat = _catalog({"m-1": _model("F1", "q1")})
    with pytest.raises(rp.QuorumUnavailable) as err:
        rp.resolve_pool("judge", 2, catalog=cat, seed="s")
    assert err.value.reason == "insufficient_candidates"


def test_free_suffix_excluded_with_reason() -> None:
    cat = _catalog(
        {
            "m-1": _model("F1", "q1"),
            "m-1-free": _model("F2", "q2"),
            "m-2": _model("F3", "q3"),
        }
    )
    lock = rp.resolve_pool("judge", 2, catalog=cat, seed="s")
    assert lock.excluded["m-1-free"] == "denied"
    assert {s.model for s in lock.primary} == {"m-1", "m-2"}
    verdicts = {row["model"]: row["verdict"] for row in lock.lock["considered"]}
    assert verdicts["m-1-free"] == "excluded:denied"


def test_temp_off_and_denied_sets_and_exclude() -> None:
    cat = _catalog({"m-%d" % i: _model("F%d" % i, "q%d" % i) for i in range(1, 6)})
    lock = rp.resolve_pool(
        "judge",
        2,
        catalog=cat,
        seed="s",
        temp_off=["m-1"],
        denied=["m-2"],
        exclude=["m-3"],
    )
    assert lock.excluded == {"m-1": "temp_off", "m-2": "denied", "m-3": "excluded"}


def test_quarantine_excluded_for_gated_allowed_for_worker() -> None:
    cat = _catalog(
        {
            "m-ok": _model("F1", "q1"),
            "m-q": _model("F2", "q2", status="quarantine"),
            "m-s": _model("F3", "q3", status="stale"),
        }
    )
    coder = rp.resolve_pool("coder", 1, distinct_family=False, catalog=cat, seed="s")
    assert coder.excluded == {"m-q": "status", "m-s": "status"}
    assert [s.model for s in coder.primary] == ["m-ok"]
    worker = rp.resolve_pool("worker", 3, distinct_family=False, catalog=cat, seed="s")
    assert worker.excluded == {}
    assert {s.model for s in worker.primary} == {"m-ok", "m-q", "m-s"}


def test_quorum_requires_family_and_eligibility() -> None:
    nofam = _model("", "q2")
    cat = _catalog(
        {"m-1": _model("F1", "q1"), "m-nofam": nofam, "m-3": _model("F3", "q3")}
    )
    lock = rp.resolve_pool("judge", 2, catalog=cat, seed="s")
    assert lock.excluded["m-nofam"] == "not_eligible"
    cat2 = _catalog(
        {
            "m-1": _model("F1", "q1"),
            "m-2": dict(_model("F2", "q2"), quorum_eligible=False),
        }
    )
    with pytest.raises(rp.QuorumUnavailable):
        rp.resolve_pool("judge", 2, catalog=cat2, seed="s")


def _with_receipt(
    tmp_path: Path, verdict: str = "confirmed", tamper: bool = False
) -> Any:
    probes = tmp_path / "probes"
    probes.mkdir()
    raw = json.dumps({"verdict": verdict, "model": "m-1"}).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    (probes / ("%s.json" % sha)).write_bytes(raw + (b" " if tamper else b""))
    return probes, sha


def test_confirmed_without_receipt_file_is_excluded(tmp_path: Path) -> None:
    probes, sha = _with_receipt(tmp_path)
    missing = "a" * 64
    cat = _catalog(
        {
            "m-1": _model("F1", "q1", receipt=sha),
            "m-2": _model("F2", "q2", receipt=missing),
            "m-3": _model("F3", "q3", receipt=sha),
        }
    )
    lock = rp.resolve_pool("judge", 2, catalog=cat, seed="s", probes_dir=str(probes))
    assert lock.excluded == {"m-2": "receipt"}
    # worker (open) квитанцию не проверяет, но проверка явно отключаема и для gated
    off = rp.resolve_pool(
        "judge", 3, catalog=cat, seed="s", probes_dir=str(probes), verify_receipts=False
    )
    assert off.excluded == {}


def test_receipt_hash_mismatch_and_bad_verdict_excluded(tmp_path: Path) -> None:
    probes, sha = _with_receipt(tmp_path, tamper=True)
    cat = _catalog({"m-1": _model("F1", "q1", receipt=sha), "m-2": _model("F2", "q2")})
    lock = rp.resolve_pool(
        "coder", 1, distinct_family=False, catalog=cat, seed="s", probes_dir=str(probes)
    )
    assert lock.excluded == {"m-1": "receipt"}
    probes2 = tmp_path / "p2"
    probes2.mkdir()
    raw = json.dumps({"verdict": "failed"}).encode("utf-8")
    sha2 = hashlib.sha256(raw).hexdigest()
    (probes2 / ("%s.json" % sha2)).write_bytes(raw)
    cat2 = _catalog({"m-1": _model("F1", "q1", receipt=sha2)})
    lock2 = rp.resolve_pool(
        "worker", 1, catalog=cat2, seed="s", probes_dir=str(probes2)
    )
    assert lock2.excluded == {}  # open-роль квитанции не требует
    with pytest.raises(rp.QuorumUnavailable):
        rp.resolve_pool("coder", 1, catalog=cat2, seed="s", probes_dir=str(probes2))


def test_probes_dir_from_env_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    probes = tmp_path / "state" / "probes"
    probes.mkdir(parents=True)
    cat = _catalog(
        {"m-1": _model("F1", "q1", receipt="b" * 64), "m-2": _model("F2", "q2")}
    )
    lock = rp.resolve_pool("coder", 1, distinct_family=False, catalog=cat, seed="s")
    assert lock.excluded == {"m-1": "receipt"}


def test_fingerprint_mismatch_excluded(tmp_path: Path) -> None:
    probes, sha = _with_receipt(tmp_path)
    cat = _catalog(
        {
            "m-1": _model("F1", "q1", receipt=sha, fp="0" * 64),
            "m-2": _model("F2", "q2", receipt=sha),
        }
    )
    lock = rp.resolve_pool(
        "coder", 1, distinct_family=False, catalog=cat, seed="s", probes_dir=str(probes)
    )
    assert lock.excluded == {"m-1": "fingerprint"}


def test_determinism_and_lock_sha_verifies() -> None:
    a = rp.resolve_pool("judge", 3, catalog=FOUR, seed="s1")
    b = rp.resolve_pool("judge", 3, catalog=json.loads(json.dumps(FOUR)), seed="s1")
    assert a.lock_sha256 == b.lock_sha256
    assert rp.canonical_bytes(a.lock) == rp.canonical_bytes(b.lock)
    assert rp.verify_lock_sha256(a.lock)
    body = {k: v for k, v in a.lock.items() if k != "lock_sha256"}
    canon = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert hashlib.sha256(canon).hexdigest() == a.lock_sha256
    tampered = dict(a.lock, seed="other")
    assert not rp.verify_lock_sha256(tampered)
    other_seed = rp.resolve_pool("judge", 3, catalog=FOUR, seed="s2")
    assert other_seed.lock_sha256 != a.lock_sha256


def test_lock_schema_fields() -> None:
    lock = rp.resolve_pool("judge", 3, catalog=FOUR, seed="s").lock
    assert lock["schema"] == "pool-lock/1"
    assert lock["resolver_version"] == 1
    for key in (
        "role",
        "n",
        "distinct_family",
        "distinct_quota",
        "degraded_mode",
        "seed",
        "inputs",
    ):
        assert key in lock
    assert len(lock["inputs"]["catalog_lock_sha256"]) == 64
    assert {"model", "effort", "rank", "verdict"} <= set(lock["considered"][0])
    seat = lock["primary"][0]
    assert set(seat) == {
        "model",
        "effort",
        "family",
        "quota_group",
        "provider",
        "status",
        "probe_receipt_sha256",
        "reserve",
    }
    assert seat["effort"] == "high"


def test_config_path_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cat.json"
    path.write_text(json.dumps(FOUR), encoding="utf-8")
    from_arg = rp.resolve_pool("judge", 3, config_path=str(path), seed="s")
    monkeypatch.setenv(rp.ENV_CATALOG_LOCK, str(path))
    from_env = rp.resolve_pool("judge", 3, seed="s")
    assert from_arg.lock_sha256 == from_env.lock_sha256
    with pytest.raises(rp.PolicyError):
        rp.resolve_pool("judge", 3, config_path=str(tmp_path / "nope.json"), seed="s")


def test_write_lock_excl_second_write_raises(tmp_path: Path) -> None:
    target = tmp_path / "run" / "pool.lock.json"
    result = rp.resolve_pool(
        "judge", 3, catalog=FOUR, seed="s", write_lock_to=str(target)
    )
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == result.lock
    assert rp.verify_lock_sha256(written)
    assert (
        target.parent / "pool-inputs" / written["inputs"]["catalog_lock_sha256"]
    ).is_file()
    with pytest.raises(FileExistsError):
        rp.resolve_pool("judge", 3, catalog=FOUR, seed="s", write_lock_to=str(target))


def test_degraded_mode_rules() -> None:
    cat = _catalog({"m-1": _model("F1", "q1"), "m-2": _model("F1", "q2")})
    with pytest.raises(rp.PolicyError):
        rp.resolve_pool("judge", 2, distinct_family=False, catalog=cat, seed="s")
    with pytest.raises(rp.PolicyError):
        rp.resolve_pool(
            "judge",
            2,
            distinct_family=False,
            degraded_mode="OTHER",
            catalog=cat,
            seed="s",
        )
    ok = rp.resolve_pool(
        "judge",
        2,
        distinct_family=False,
        degraded_mode="QUORUM_DEGRADED_HATS",
        catalog=cat,
        seed="s",
    )
    assert len(ok.primary) == 2 and ok.lock["degraded_mode"] == "QUORUM_DEGRADED_HATS"
    # не-кворумные роли в degraded_mode не нуждаются
    assert (
        len(
            rp.resolve_pool(
                "coder", 2, distinct_family=False, catalog=cat, seed="s"
            ).primary
        )
        == 2
    )
    with pytest.raises(rp.PolicyError):
        rp.resolve_pool("judge", 0, catalog=cat, seed="s")


def test_max_candidates_env_caps_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(rp.ENV_MAX_CANDIDATES, "2")
    with pytest.raises(rp.QuorumUnavailable):
        rp.resolve_pool("judge", 3, catalog=FOUR, seed="s")


def test_effort_default_selection() -> None:
    assert (
        rp.pick_default_effort({"efforts_proven": ["low", "medium", "high"]}) == "high"
    )
    assert rp.pick_default_effort({"efforts_proven": [], "efforts": ["x", "y"]}) == "x"
    assert rp.pick_default_effort({}) == ""
    os.environ[rp.ENV_EFFORT_ORDER] = "high,medium,low"
    try:
        assert rp.pick_default_effort({"efforts_proven": ["low", "high"]}) == "low"
    finally:
        del os.environ[rp.ENV_EFFORT_ORDER]


def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    path = tmp_path / "cat.json"
    path.write_text(json.dumps(FOUR), encoding="utf-8")
    assert (
        rp.main(["--role", "judge", "--n", "3", "--seed", "s", "--config", str(path)])
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == "pool-lock/1" and len(out["primary"]) == 3
    assert (
        rp.main(["--role", "judge", "--n", "4", "--seed", "s", "--config", str(path)])
        == 2
    )
    err = json.loads(capsys.readouterr().out)
    assert err["error"] == "quorum_unavailable"
    assert (
        rp.main(
            [
                "--role",
                "judge",
                "--n",
                "2",
                "--no-distinct-family",
                "--config",
                str(path),
            ]
        )
        == 3
    )
    assert (
        rp.main(
            ["--role", "judge", "--n", "2", "--config", str(tmp_path / "missing.json")]
        )
        == 3
    )
    with pytest.raises(SystemExit) as exc:
        rp.main(["--n", "2"])
    assert exc.value.code == 3
    assert (
        rp.main(
            [
                "--role",
                "judge",
                "--n",
                "2",
                "--no-distinct-family",
                "--degraded-mode",
                "QUORUM_DEGRADED_HATS",
                "--config",
                str(path),
                "--write-lock",
                str(tmp_path / "lk" / "pool.lock.json"),
            ]
        )
        == 0
    )
    assert (tmp_path / "lk" / "pool.lock.json").is_file()

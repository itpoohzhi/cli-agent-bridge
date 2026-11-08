from __future__ import annotations

# Быстрые детерминированные проверки `core/catalog_promote.py`: атомарный промоушен под flock,
# продвижение записи до `confirmed`, post-verify сайдкара и карта отказов в slug.

import dataclasses
import fcntl
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from core import catalog_promote as promote  # noqa: E402
from core.discovery import DiscoveryResult  # noqa: E402
from core.fleet_compiler import CompileError  # noqa: E402
from core.model_lifecycle import (  # noqa: E402
    STATUS_CONFIRMED,
    STATUS_QUARANTINE_FAILED,
    LifecycleError,
    LifecycleRegistry,
    ModelRecord,
)

PROVIDERS = ROOT / "providers.d"
FP = "f" * 64
REQ = promote.PromoteRequest("droid", "gpt-6.1-sol", "r" * 64, FP, ("high",))


@pytest.mark.parametrize("obj", [REQ, promote.LockPolicy(1.0, 0.1)])
def test_wave_dataclasses_are_frozen_and_slotted(obj: Any) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, dataclasses.fields(obj)[0].name, "x")
    assert not hasattr(obj, "__dict__")


def test_promote_request_from_probe_copies_receipt_fields() -> None:
    result: Any = SimpleNamespace(
        receipt_sha256="r" * 64, fingerprint_sha256=FP, efforts_proven=["high"]
    )
    assert promote.PromoteRequest.from_probe(result, "droid", "gpt-6.1-sol") == REQ


@pytest.mark.parametrize(
    "raw,expected", [(None, 3.0), ("abc", 3.0), ("-5", 0.0), ("2.5", 2.5)]
)
def test_lock_policy_from_env_clamps_and_falls_back(
    raw: str | None, expected: float
) -> None:
    env = {} if raw is None else {promote.ENV_LOCK_WAIT: raw}
    assert promote._env_float(env, promote.ENV_LOCK_WAIT, 3.0) == expected
    policy = promote.LockPolicy.from_env({})
    assert (policy.wait_s, policy.poll_s) == (30.0, 0.05)


def test_lifecycle_lock_creates_directory_and_enters_without_waiting(
    tmp_path: Path,
) -> None:
    state = tmp_path / "a" / "b"
    for _ in range(2):
        with promote.lifecycle_lock(state, promote.LockPolicy(0.0, 0.05)):
            assert (state / ".lifecycle.lock").is_file()


def test_lifecycle_lock_busy_raises_slug(tmp_path: Path) -> None:
    fd = os.open(tmp_path / ".lifecycle.lock", os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        with pytest.raises(promote.PromoteError) as caught:
            with promote.lifecycle_lock(tmp_path, promote.LockPolicy(0.05, 0.01)):
                pass
    finally:
        os.close(fd)
    assert caught.value.slug == "lifecycle_lock_busy"


# ---- реестр жизненного цикла ----------------------------------------------------------


def test_advance_confirms_once_and_repeat_is_noop() -> None:
    registry = LifecycleRegistry()
    first = promote.advance_to_confirmed(registry, REQ, 1.0)
    assert (first.status, first.receipt_sha256) == (STATUS_CONFIRMED, "r" * 64)
    assert first.efforts_proven == ("high",)
    with mock.patch.object(registry, "apply") as apply:
        assert promote.advance_to_confirmed(registry, REQ, 2.0) is first
    apply.assert_not_called()
    newer = dataclasses.replace(REQ, receipt_sha256="x" * 64)
    again = promote.advance_to_confirmed(registry, newer, 3.0)
    assert (again.status, again.receipt_sha256) == (STATUS_CONFIRMED, "x" * 64)


def test_advance_forces_probe_before_retry_after() -> None:
    failed = ModelRecord(
        "droid", "gpt-6.1-sol", FP, STATUS_QUARANTINE_FAILED, retry_after=1e12
    )
    done = promote.advance_to_confirmed(LifecycleRegistry([failed]), REQ, 1.0)
    assert done.status == STATUS_CONFIRMED


def test_discovery_fingerprints_known_providers_and_proves_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        promote, "compute_fingerprint", lambda m, env: "fp-" + m.provider_id
    )
    registry = LifecycleRegistry()
    registry.register("codex", "gpt-6.1-terra", "c" * 64)
    found = promote._discovery(REQ, registry, PROVIDERS, {})
    assert found == {
        "codex": DiscoveryResult("codex", "fp-codex"),
        "droid": DiscoveryResult("droid", FP),
    }


def test_write_compiled_state_renders_sorted_unicode_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(promote, "render_fleet_json", lambda fleet: b"{}")
    result: Any = SimpleNamespace(fleet={}, sidecar={"b": 1, "a": "модель"})
    promote.write_compiled_state(result, tmp_path / "f.json", tmp_path / "s.json")
    assert (tmp_path / "f.json").read_bytes() == b"{}"
    text = (tmp_path / "s.json").read_text(encoding="utf-8")
    assert text == '{\n  "a": "модель",\n  "b": 1\n}\n'


@pytest.mark.parametrize(
    "content,expected",
    [
        ('{"models": {"m": {"status": "confirmed"}}}', True),
        ('{"models": {"m": {"status": "quarantine"}}}', False),
        ('{"models": {}}', False),
        ('{"models": []}', False),
        ("[]", False),
        ("not json", False),
        (None, False),
    ],
)
def test_confirmed_in_sidecar_is_fail_closed(
    tmp_path: Path, content: str | None, expected: bool
) -> None:
    path = tmp_path / "side.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert promote._confirmed_in_sidecar(path, "m") is expected


def _stub_compile(monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    sidecar = {"models": {REQ.model_id: {"status": status}}}
    monkeypatch.setattr(
        promote, "compile_from_disk", lambda *a, **k: SimpleNamespace(sidecar=sidecar)
    )
    monkeypatch.setattr(
        promote,
        "write_compiled_state",
        lambda result, fleet, side: Path(side).write_text(json.dumps(result.sidecar)),
    )
    monkeypatch.setattr(promote, "compute_fingerprint", lambda m, env: "fp")


def test_promote_locked_post_verifies_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_compile(monkeypatch, "confirmed")
    promote._promote_locked(REQ, tmp_path, PROVIDERS, {})
    saved = LifecycleRegistry.load(tmp_path / promote.REGISTRY_FILE).records()
    assert [r.status for r in saved] == [STATUS_CONFIRMED]
    _stub_compile(monkeypatch, "quarantine")
    (tmp_path / "second").mkdir()
    with pytest.raises(promote.PromoteError) as caught:
        promote._promote_locked(REQ, tmp_path / "second", PROVIDERS, {})
    assert caught.value.slug == "post_verify_mismatch"


@pytest.mark.parametrize(
    "error,slug",
    [
        (promote.PromoteError("busy"), "busy"),
        (LifecycleError("x"), "lifecycle_error"),
        (CompileError("bad"), "compile_error:bad"),
        (OSError("io"), "state_io_error"),
    ],
)
def test_promote_confirmed_maps_failures_to_slugs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, slug: str
) -> None:
    monkeypatch.setattr(promote, "_promote_locked", mock.Mock(side_effect=error))
    assert promote.promote_confirmed(REQ, tmp_path, env={}) == slug


def test_promote_confirmed_passes_given_env_else_process_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked = mock.Mock()
    monkeypatch.setattr(promote, "_promote_locked", locked)
    env = {promote.ENV_LOCK_WAIT: "0"}
    assert (
        promote.promote_confirmed(REQ, tmp_path, providers_dir=tmp_path, env=env) == ""
    )
    assert locked.call_args.args == (REQ, tmp_path, tmp_path, env)
    assert promote.promote_confirmed(REQ, tmp_path) == ""
    assert locked.call_args.args[3] is os.environ


# ---- all-or-nothing: сбой компиляции или записи не оставляет частичного состояния ------------


def _seed_state(state: Path) -> dict[Path, bytes]:
    """Реестр с моделью в `quarantine` и старые `fleet.compiled.json`/`catalog.lock.json`."""
    registry = LifecycleRegistry()
    registry.register(REQ.provider_id, REQ.model_id, FP)
    registry.save(state / promote.REGISTRY_FILE)
    for name, data in ((promote.COMPILED_FLEET_FILE, b'{"old": 1}'), (promote.SIDECAR_FILE, b'{"old": 2}')):
        (state / name).write_bytes(data)
    return {p: p.read_bytes() for p in state.iterdir() if p.name != promote.LOCK_FILE}


def _bytes_on_disk(state: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in state.iterdir() if p.name != promote.LOCK_FILE}


def test_compile_error_leaves_all_state_files_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _seed_state(tmp_path)
    _stub_compile(monkeypatch, "confirmed")
    monkeypatch.setattr(
        promote, "compile_from_disk", mock.Mock(side_effect=CompileError("qa_injected"))
    )
    assert promote.promote_confirmed(REQ, tmp_path, env={}) == "compile_error:qa_injected"
    assert _bytes_on_disk(tmp_path) == before
    saved = LifecycleRegistry.load(tmp_path / promote.REGISTRY_FILE).records()
    assert [r.status for r in saved] != [STATUS_CONFIRMED]


def test_second_write_failure_rolls_back_all_three_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _seed_state(tmp_path)
    sidecar = {"models": {REQ.model_id: {"status": "confirmed"}}}
    monkeypatch.setattr(promote, "compute_fingerprint", lambda m, env: "fp")
    monkeypatch.setattr(promote, "render_fleet_json", lambda fleet: b'{"new": 1}')
    monkeypatch.setattr(
        promote,
        "compile_from_disk",
        lambda *a, **k: SimpleNamespace(fleet={}, sidecar=sidecar),
    )
    real, calls = promote.atomic_write_bytes, []

    def flaky(path: Path, data: bytes) -> None:
        calls.append(path.name)
        if len(calls) == 2:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(promote, "atomic_write_bytes", flaky)
    assert promote.promote_confirmed(REQ, tmp_path, env={}).startswith("state_io_error")
    assert calls[:2] == [promote.COMPILED_FLEET_FILE, promote.SIDECAR_FILE]
    assert _bytes_on_disk(tmp_path) == before


def test_post_verify_mismatch_rolls_back_and_missing_files_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = LifecycleRegistry()
    registry.register(REQ.provider_id, REQ.model_id, FP)
    registry.save(tmp_path / promote.REGISTRY_FILE)
    before = _bytes_on_disk(tmp_path)
    _stub_compile(monkeypatch, "quarantine")
    monkeypatch.setattr(
        promote,
        "write_compiled_state",
        lambda result, fleet, side: (
            Path(fleet).write_text("{}"),
            Path(side).write_text(json.dumps(result.sidecar)),
        ),
    )
    assert promote.promote_confirmed(REQ, tmp_path, env={}) == "post_verify_mismatch"
    assert _bytes_on_disk(tmp_path) == before

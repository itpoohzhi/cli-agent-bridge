from __future__ import annotations

# Откат промоушена: отказ записи и отказ восстановления не оставляют реестр в `confirmed`; дедлайн блокировки.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import catalog_promote as promote  # noqa: E402
from core.model_lifecycle import STATUS_CONFIRMED, LifecycleRegistry  # noqa: E402
from test_catalog_promote_units import REQ, _bytes_on_disk, _seed_state  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport, reportPrivateUsage]


def _inject_failures(
    monkeypatch: pytest.MonkeyPatch, *, fail_write_at: int | None, fail_restore: bool, fail_registry: bool
) -> None:
    """Отказ записи каталога, отказ отката и/или отказ записи реестра (реестр пишется последним)."""
    sidecar = {"models": {REQ.model_id: {"status": "confirmed"}}}
    monkeypatch.setattr(promote, "compute_fingerprint", lambda m, env: "fp")
    monkeypatch.setattr(promote, "render_fleet_json", lambda fleet: b'{"new": 1}')
    monkeypatch.setattr(
        promote, "compile_from_disk", lambda *a, **k: SimpleNamespace(fleet={}, sidecar=sidecar)
    )
    real, calls = promote.atomic_write_bytes, []

    def flaky(path: Path, data: bytes) -> None:
        calls.append(path.name)
        if (fail_write_at is not None and len(calls) == fail_write_at) or (
            fail_restore and len(calls) > (fail_write_at or 2)
        ):
            raise OSError("injected")
        real(path, data)

    monkeypatch.setattr(promote, "atomic_write_bytes", flaky)
    if fail_registry:
        monkeypatch.setattr(LifecycleRegistry, "save", mock.Mock(side_effect=OSError("registry")))


def _registry_statuses(state: Path) -> list[str]:
    return [r.status for r in LifecycleRegistry.load(state / promote.REGISTRY_FILE).records()]


def test_rollback_failure_after_write_failure_never_leaves_registry_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _seed_state(tmp_path)
    _inject_failures(monkeypatch, fail_write_at=2, fail_restore=True, fail_registry=False)
    assert promote.promote_confirmed(REQ, tmp_path, env={}) == "rollback_failed"
    assert STATUS_CONFIRMED not in _registry_statuses(tmp_path)
    reg = tmp_path / promote.REGISTRY_FILE
    assert reg.read_bytes() == before[reg]


def test_registry_write_failure_restores_catalog_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _seed_state(tmp_path)
    _inject_failures(monkeypatch, fail_write_at=None, fail_restore=False, fail_registry=True)
    assert promote.promote_confirmed(REQ, tmp_path, env={}) == "state_io_error"
    assert _bytes_on_disk(tmp_path) == before


def test_registry_write_and_rollback_failure_reports_rollback_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _seed_state(tmp_path)
    _inject_failures(monkeypatch, fail_write_at=None, fail_restore=True, fail_registry=True)
    assert promote.promote_confirmed(REQ, tmp_path, env={}) == "rollback_failed"
    reg = tmp_path / promote.REGISTRY_FILE
    assert reg.read_bytes() == before[reg] and STATUS_CONFIRMED not in _registry_statuses(tmp_path)

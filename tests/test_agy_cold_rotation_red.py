"""W0 red repros for agy cold rotation (I1) and the unified lifecycle budget (I2).

Dual-mode contract — the file never skips a test:
- ``LOSS_CONTRACT_RED=1`` while a defect is still present: the affected tests
  are strict xfails (``raises=AssertionError``), the red repro of F-08/F-04/F-05.
- Otherwise (default, post-W2): every test runs as a real assertion of the
  target behaviour, so the same file turns green once the fix lands.

Defect probes reuse the same fake pool as the tests (no real processes,
sockets or env writes); they only gate the xfail marker and never relax an
assertion.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime.loss_contract_config import worker_bounds  # noqa: E402
from agy_runtime.persistent_worker_adapter import (  # noqa: E402
    AgyPersistentWorkerPool,
    PersistentAcquireRequest,
    PersistentReleaseParams,
)
from agy_runtime.persistent_worker_config import (  # noqa: E402
    PersistentWorkerSettings,
    persistent_worker_settings,
)
from agy_runtime.session_resume_adapter import read_runtime_flags  # noqa: E402

_RED: Final = os.environ.get("LOSS_CONTRACT_RED") == "1"


class _StableHandle:
    generation = 0
    proc = SimpleNamespace(pid=41701)

    def is_alive(self) -> bool:
        return True

    def read_stdout_line_outcome(self, timeout_s: float) -> tuple[str, None]:
        assert timeout_s == 0.0
        return ("timeout", None)


class _Entry:
    slot_id = "slot-0"
    lease_id = "lease-0"
    handle = _StableHandle()


class _StablePool:
    def __init__(self) -> None:
        self.entry = _Entry()
        self.release_calls: list[tuple[str, bool, bool, str]] = []

    def acquire(self, *_args: object, **_kwargs: object) -> _Entry:
        return self.entry

    def release(self, slot_id: str, *, success: bool, cancel: bool, lease_id: str) -> None:
        self.release_calls.append((slot_id, success, cancel, lease_id))


def _request(*, chat_key: str, cid: str) -> PersistentAcquireRequest:
    return PersistentAcquireRequest(
        chat_key=chat_key,
        cid=cid,
        model="test-model",
        effort="high",
        cwd="/tmp/agy-red",
        env_digest="env-digest",
        review_profile="standard",
        argv_builder=lambda: ["agy", "--test"],
        env={},
    )


def _fixture_pool() -> tuple[AgyPersistentWorkerPool, _StablePool, PersistentWorkerSettings]:
    adapter = AgyPersistentWorkerPool()
    backend = _StablePool()
    adapter._pool = backend  # type: ignore[assignment]
    adapter._ensure_pool = lambda _cfg: backend  # type: ignore[method-assign]
    cfg = PersistentWorkerSettings(enabled=True, max_turns=30)
    return adapter, backend, cfg


def _release(
    adapter: AgyPersistentWorkerPool,
    lease: object,
    *,
    cid: str,
) -> None:
    adapter.release(
        lease,  # type: ignore[arg-type]
        PersistentReleaseParams(success=True, cid=cid, max_slots=1),
    )


def _worker_budget() -> int:
    """Эффективный бюджет воркера: unified clamp поверх legacy-ридера (AD-003)."""
    settings = persistent_worker_settings(config_path=None)
    return worker_bounds(settings, config_path=None).max_turns


def _reuse_defect(first: tuple[str, str], second: tuple[str, str]) -> bool:
    """True, если сценарий всё ещё переиспользует живой слот (дофиксовый I1)."""
    try:
        adapter, _backend, cfg = _fixture_pool()
        first_lease = adapter.acquire(_request(chat_key=first[0], cid=first[1]), cfg)
        if first_lease is None:
            return False
        _release(adapter, first_lease, cid=first[1])
        second_lease = adapter.acquire(_request(chat_key=second[0], cid=second[1]), cfg)
        return second_lease is not None
    except Exception:
        return True


def _lifecycle_defect() -> bool:
    """True, если эффективный бюджет воркера ещё не унифицирован до 30 (I2)."""
    try:
        return _worker_budget() != 30
    except Exception:
        return True


def _red_mark(defect: bool, reason: str) -> pytest.MarkDecorator:
    """Strict xfail только в red-режиме и пока дефект воспроизводится; иначе реальные ассерты."""
    return pytest.mark.xfail(
        condition=_RED and defect, strict=True, raises=AssertionError, reason=reason
    )


def _assert_evicted(backend: _StablePool) -> None:
    assert ("slot-0", False, True, "lease-0") in backend.release_calls, (
        "rotation must evict the slot through release(cancel=True)"
    )


@_red_mark(
    _reuse_defect(("cold-chat", ""), ("cold-chat", "")),
    "I1 red: cold cid='' still reuses the live PID",
)
def test_cold_request_with_empty_cid_does_not_reuse_live_pid() -> None:
    adapter, backend, cfg = _fixture_pool()
    first = adapter.acquire(_request(chat_key="cold-chat", cid=""), cfg)
    assert first is not None
    _release(adapter, first, cid="")

    second = adapter.acquire(_request(chat_key="cold-chat", cid=""), cfg)

    assert second is None, "a stateless request must take a one-shot cold spawn"
    _assert_evicted(backend)


@_red_mark(
    _reuse_defect(("shared-chat", "cid-a"), ("shared-chat", "cid-b")),
    "I1 red: mismatched cid still reuses the previous slot",
)
def test_mismatched_cid_does_not_reuse_the_previous_slot() -> None:
    adapter, backend, cfg = _fixture_pool()
    first = adapter.acquire(_request(chat_key="shared-chat", cid="cid-a"), cfg)
    assert first is not None
    _release(adapter, first, cid="cid-a")

    second = adapter.acquire(_request(chat_key="shared-chat", cid="cid-b"), cfg)

    assert second is None, "a slot bound to cid-a cannot serve cid-b"
    _assert_evicted(backend)


@_red_mark(
    _reuse_defect(("anchored-chat", "cid-text"), ("", "cid-text")),
    "I1 red: unanchored text-only retry still reuses the slot",
)
def test_text_only_retry_without_resume_anchor_does_not_reuse_slot() -> None:
    adapter, backend, cfg = _fixture_pool()
    first = adapter.acquire(_request(chat_key="anchored-chat", cid="cid-text"), cfg)
    assert first is not None
    _release(adapter, first, cid="cid-text")

    # A text-only retry carries the cid but no chat-key/transcript anchor.
    second = adapter.acquire(_request(chat_key="", cid="cid-text"), cfg)

    assert second is None, "an unanchored retry must rotate to a cold worker"
    _assert_evicted(backend)


@pytest.mark.parametrize(
    "case",
    ("default", "hot-policy", "lifecycle-env"),
)
@_red_mark(_lifecycle_defect(), "I2 red: worker max_turns is not unified to 30 yet")
def test_all_three_lifecycle_max_turns_sources_are_thirty(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    monkeypatch.delenv("AGY_BRIDGE_PERSISTENT_MAX_TURNS", raising=False)
    monkeypatch.delenv("AGY_BRIDGE_LIFECYCLE_MAX_TURNS", raising=False)
    monkeypatch.delenv("AGY_BRIDGE_UNIFIED_LIFECYCLE_ENABLED", raising=False)
    monkeypatch.delenv("BRIDGE_HOT_MAX_TURNS", raising=False)

    if case == "default":
        expected = 30
    elif case == "hot-policy":
        expected = read_runtime_flags().policy.max_turns
        assert expected == 30, "hot policy must resolve the unified 30-turn budget"
    else:
        monkeypatch.setenv("AGY_BRIDGE_LIFECYCLE_MAX_TURNS", "30")
        expected = 30

    assert _worker_budget() == expected, "worker budget must equal the lifecycle budget"

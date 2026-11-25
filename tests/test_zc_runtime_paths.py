"""Unit-тесты модуля zc_runtime_paths (AD-002 / BUG-B2, RISK-B3)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
for _p in (str(ROOT), str(BRIDGE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agy_runtime.session_store import CommitPayload, ExplicitSessionStore  # noqa: E402
from agy_runtime.zc_runtime_paths import (  # noqa: E402
    collect_protected_zc_cids,
    resolve_agy_runtime_dirs,
)
from core.hot_session_policy import PolicyConfig  # noqa: E402


class _Adapter:
    def __init__(self, store: Any) -> None:
        self._store = store


def _payload(key: str, cid: str, now_s: float, *, slen: int = 2) -> CommitPayload:
    return CommitPayload(
        key=key,
        owner_token_hash="owner-h1",
        cid=cid,
        stored_digest=f"dig-{slen}",
        stored_len=slen,
        stored_asst=1,
        epoch=1,
        now_s=now_s,
    )


def test_resolve_dirs_zero_canon_default_and_explicit_zc_home() -> None:
    clean_home = Path("/tmp/agy-home")
    conv, brain = resolve_agy_runtime_dirs(
        True,
        clean_home=clean_home,
        default_conv_dir=Path("/ignored/conv"),
        default_brain_dir=Path("/ignored/brain"),
    )
    assert conv == Path("/tmp/agy-home-zc/.gemini/antigravity-cli/conversations")
    assert brain == Path("/tmp/agy-home-zc/.gemini/antigravity-cli/brain")

    zc_home = Path("/var/tmp/custom-zc")
    conv_zc, brain_zc = resolve_agy_runtime_dirs(True, clean_home=clean_home, zc_home=zc_home)
    assert conv_zc == zc_home / ".gemini" / "antigravity-cli" / "conversations"
    assert brain_zc == zc_home / ".gemini" / "antigravity-cli" / "brain"


def test_resolve_dirs_non_zero_canon_defaults_and_overrides() -> None:
    clean_home = Path("/tmp/agy-home")
    conv, brain = resolve_agy_runtime_dirs(False, clean_home=clean_home, zc_home=Path("/ignored-zc"))
    assert conv == clean_home / ".gemini" / "antigravity-cli" / "conversations"
    assert brain == clean_home / ".gemini" / "antigravity-cli" / "brain"

    custom_conv, custom_brain = Path("/data/conv"), Path("/data/brain")
    assert resolve_agy_runtime_dirs(
        False,
        clean_home=clean_home,
        default_conv_dir=custom_conv,
        default_brain_dir=custom_brain,
    ) == (custom_conv, custom_brain)

    partial_conv, partial_brain = resolve_agy_runtime_dirs(False, clean_home=clean_home, default_conv_dir=custom_conv)
    assert partial_conv == custom_conv
    assert partial_brain == clean_home / ".gemini" / "antigravity-cli" / "brain"


def test_collect_protected_zc_cids_merges_in_flight_and_active_store_slots(tmp_path: Path) -> None:
    store = ExplicitSessionStore(tmp_path, policy=PolicyConfig(enabled=True, idle_ttl_s=60.0, max_ttl_s=300.0), epoch=1)
    try:
        assert store.commit_pending(_payload("k-active", "cid-active", 1000.0)) is True
        assert store.flush_now() is True
        protected = collect_protected_zc_cids(["cid-flight", "", "cid-active"], _Adapter(store), now_s=1010.0)
        assert protected == frozenset({"cid-flight", "cid-active"})
    finally:
        store.close()


def test_collect_protected_zc_cids_excludes_expired_without_lease_keeps_leased(tmp_path: Path) -> None:
    store = ExplicitSessionStore(tmp_path, policy=PolicyConfig(enabled=True, idle_ttl_s=10.0, max_ttl_s=50.0), epoch=1)
    try:
        assert store.commit_pending(_payload("k-idle-exp", "cid-idle-exp", 100.0)) is True
        assert store.commit_pending(_payload("k-max-exp", "cid-max-exp", 100.0, slen=2)) is True
        assert store.commit_pending(_payload("k-max-exp", "cid-max-exp", 145.0, slen=5)) is True
        assert store.commit_pending(_payload("k-leased", "cid-leased", 100.0)) is True
        assert store.flush_now() is True
        assert store.claim_resume("k-leased", "cid-leased", 100.0, 1)

        protected = collect_protected_zc_cids(["cid-inflight"], _Adapter(store), now_s=151.0)
        assert protected == frozenset({"cid-inflight", "cid-leased"})
    finally:
        store.close()


def test_collect_protected_zc_cids_tolerates_none_and_broken_store() -> None:
    class _BrokenStoreAttr:
        @property
        def _store(self) -> Any:
            raise RuntimeError("store access failed")

    class _BrokenLock:
        def __enter__(self) -> None:
            raise RuntimeError("lock failed")

        def __exit__(self, *_args: object) -> None:
            return None

    class _StoreWithBrokenLock:
        _lock = _BrokenLock()
        _slots: dict[str, Any] = {}

    class _StoreWithBadSlots:
        _slots = None

    assert collect_protected_zc_cids(["cid-1", ""], None) == frozenset({"cid-1"})
    assert collect_protected_zc_cids(["cid-1"], _Adapter(None)) == frozenset({"cid-1"})
    assert collect_protected_zc_cids(["cid-1"], _BrokenStoreAttr()) == frozenset({"cid-1"})
    assert collect_protected_zc_cids(["cid-1"], _Adapter(_StoreWithBrokenLock())) == frozenset({"cid-1"})
    assert collect_protected_zc_cids(["cid-1"], _Adapter(_StoreWithBadSlots())) == frozenset({"cid-1"})

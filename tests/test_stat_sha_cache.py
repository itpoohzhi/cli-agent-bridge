"""Unit tests for StatShaCache (Wave 3)."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import time

_CACHE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "bridges"
    / "agy-bridge"
    / "stat_sha_cache.py"
)
_SPEC = importlib.util.spec_from_file_location("agy_stat_sha_cache", _CACHE_PATH)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["agy_stat_sha_cache"] = _MOD
_SPEC.loader.exec_module(_MOD)


def test_cold_miss_sync_and_warm_hit_without_rehash(tmp_path) -> None:
    target = tmp_path / "agy.bin"
    payload = b"alpha-binary-payload"
    target.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()

    cache = _MOD.StatShaCache(chunk_bytes=8)
    assert cache.get_sha256(target) == expected

    def _boom(_self, _resolved: str):
        raise AssertionError("warm hit must not re-read file")

    cache._compute_checked = _boom.__get__(cache, _MOD.StatShaCache)  # type: ignore[method-assign]
    assert cache.get_sha256(target) == expected


def test_stat_change_returns_previous_nonblocking_then_updates(tmp_path, monkeypatch) -> None:
    target = tmp_path / "agy.bin"
    v1 = b"version-1"
    v2 = b"version-2-longer"
    v3 = b"version-3-final-payload"
    target.write_bytes(v1)
    h1 = hashlib.sha256(v1).hexdigest()
    h3 = hashlib.sha256(v3).hexdigest()

    cache = _MOD.StatShaCache(chunk_bytes=4)
    assert cache.warm_up(target) == h1

    orig_compute = cache._compute_checked
    started = {"seen": False}

    def slow_compute(resolved: str):
        if not started["seen"]:
            started["seen"] = True
            time.sleep(0.05)
            target.write_bytes(v3)
        return orig_compute(resolved)

    monkeypatch.setattr(cache, "_compute_checked", slow_compute)
    target.write_bytes(v2)

    t0 = time.monotonic()
    returned = cache.get_sha256(target)
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    assert returned == h1
    assert elapsed_ms < 15.0

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if cache.get_sha256(target) == h3:
            break
        time.sleep(0.01)
    assert cache.get_sha256(target) == h3


def test_rollback_delegates_to_legacy(tmp_path, monkeypatch) -> None:
    target = tmp_path / "agy.bin"
    target.write_bytes(b"payload")
    cache = _MOD.StatShaCache()
    monkeypatch.setenv("AGY_STAT_SHA_CACHE_ENABLED", "0")
    assert cache.get_sha256(target, legacy_fn=lambda _p: "legacy-digest") == "legacy-digest"


def test_torn_read_retries_and_returns_empty_on_persistent_churn(tmp_path, monkeypatch) -> None:
    target = tmp_path / "agy.bin"
    target.write_bytes(b"payload")
    cache = _MOD.StatShaCache(chunk_bytes=4)
    seq = iter([(1, 1, 1, 7), (1, 1, 2, 7), (1, 1, 3, 7), (1, 1, 4, 7), (1, 1, 5, 7), (1, 1, 6, 7), (1, 1, 7, 7)])
    monkeypatch.setattr(cache, "_stat_key", lambda _r: next(seq))
    assert cache.get_sha256(target) == ""

"""W5: admission/hygiene wiring in agy-bridge server.py (off-parity + delegation)."""

from __future__ import annotations

import contextlib
import hashlib
import inspect
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

try:
    from resilience_wiring_support import load_server, use_config
except ImportError:
    from tests.resilience_wiring_support import load_server, use_config

SERVER_PATH = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
BASELINE_LOC = 8294
ALL_ON: dict[str, object] = {
    "agy_adaptive_admission_enabled": True,
    "agy_fast_client_gone_enabled": True,
    "agy_bounded_state_enabled": True,
    "agy_sqlite_ro_hygiene_enabled": True,
}
ALL_OFF: dict[str, object] = {key: False for key in ALL_ON}


def _load() -> ModuleType:
    return load_server()


def _use(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cfg: dict[str, object]
) -> AbstractContextManager[Path]:
    import json

    path = use_config(monkeypatch, tmp_path, text=json.dumps(cfg))
    return contextlib.nullcontext(path)


def _fn(server: ModuleType, name: str) -> Callable[..., object]:
    return cast(Callable[..., object], getattr(server, name))


def _any_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return any(_any_true(v) for v in cast("dict[object, object]", value).values())
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(cast("list[object]", value))
        return any(_any_true(v) for v in items)
    return False


@dataclass
class FakeFlags:
    adaptive_admission_enabled: bool = False
    fast_client_gone_enabled: bool = False
    bounded_state_enabled: bool = False
    sqlite_ro_hygiene_enabled: bool = False


@dataclass
class FakeDecision:
    admitted: bool = True
    ticket_id: int = 1
    status_code: int = 200
    reason: str = "ok"


@dataclass
class FakeRT:
    flags: FakeFlags = field(default_factory=FakeFlags)
    calls: list[tuple[str, str]] = field(default_factory=list)
    sha: dict[str, str] = field(default_factory=dict)
    disconnects: list[tuple[int, bool, int]] = field(default_factory=list)
    admit_next: bool = True
    released: list[tuple[int, str]] = field(default_factory=list)

    def snapshot_flags(self, config_path: Path | None = None) -> FakeFlags:
        _ = config_path
        return self.flags

    def acquire(self, key: object, config_path: Path | None = None) -> FakeDecision:
        _ = config_path
        self.calls.append(("acquire", str(key)))
        if not self.admit_next:
            return FakeDecision(admitted=False, ticket_id=0, status_code=503, reason="shed")
        return FakeDecision(admitted=True, ticket_id=7, status_code=200, reason="ok")

    def release(self, ticket_id: int, outcome: object = None, ttfc_ms: float | None = None) -> None:
        _ = ttfc_ms
        self.released.append((ticket_id, str(outcome)))

    def sha_cache_get(self, key: str) -> str | None:
        self.calls.append(("sha_get", key))
        return self.sha.get(key) if self.flags.bounded_state_enabled else None

    def sha_cache_put(self, key: str, value: str) -> None:
        self.calls.append(("sha_put", key))
        if self.flags.bounded_state_enabled:
            self.sha[key] = value

    def session_claim(self, key: str, value: str = "1") -> bool:
        _ = value
        self.calls.append(("claim", key))
        return True

    def session_commit(self, key: str, value: str) -> None:
        _ = value
        self.calls.append(("commit", key))

    def session_invalidate(self, key: str) -> None:
        self.calls.append(("invalidate", key))

    def handle_disconnect(self, pgid: int, ttfc_received: bool, tools_count: int) -> bool:
        self.disconnects.append((pgid, ttfc_received, tools_count))
        return self.flags.fast_client_gone_enabled

    def health_snapshot(self, config_path: Path | None = None) -> dict[str, object]:
        _ = config_path
        return {
            "adaptive_admission_enabled": self.flags.adaptive_admission_enabled,
            "fast_client_gone_enabled": self.flags.fast_client_gone_enabled,
            "bounded_state_enabled": self.flags.bounded_state_enabled,
            "sqlite_ro_hygiene_enabled": self.flags.sqlite_ro_hygiene_enabled,
        }

    def shutdown_cleanup(self) -> int:
        return 0


def _install(server: ModuleType, monkeypatch: pytest.MonkeyPatch, fake: FakeRT) -> None:
    monkeypatch.setattr(server, "_HYGIENE_RT", cast(object, fake))


def test_legacy_delta_loc_non_positive() -> None:
    loc = len(SERVER_PATH.read_text(encoding="utf-8").splitlines())
    assert loc <= BASELINE_LOC, f"legacy_delta_loc={loc - BASELINE_LOC} > 0"


def test_off_mode_parity_and_six_envs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server = _load()
    _install(server, monkeypatch, FakeRT())
    with _use(monkeypatch, tmp_path, dict(ALL_OFF)):
        target = tmp_path / "blob.bin"
        _ = target.write_bytes(b"parity")
        assert _fn(server, "_file_sha256")(target) == hashlib.sha256(b"parity").hexdigest()
        resilience = cast(object, getattr(server, "midstream_resilience", None))
        if resilience is not None:
            six_envs = getattr(resilience, "SIX_ENVS", None)
            snap_attr = getattr(resilience, "flags_snapshot", None)
            if six_envs is not None and callable(snap_attr):
                snapshot_fn = cast(Callable[..., object], snap_attr)
                if len(inspect.signature(snapshot_fn).parameters) == 0:
                    snapshot = cast("dict[str, object]", snapshot_fn())
                    assert set(snapshot) == cast("set[str]", six_envs)
        source = SERVER_PATH.read_text(encoding="utf-8")
        assert '"hygiene_health"' in source


def test_hygiene_health_additive_and_dynamic_toggle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import json

    server = _load()
    monkeypatch.setattr(server, "_HYGIENE_RT", cast(object, None))
    rt = _fn(server, "_hygiene_rt")()
    health = cast(Callable[..., object], getattr(rt, "health_snapshot"))
    p_off = tmp_path / "off.json"
    p_on = tmp_path / "on.json"
    _ = p_off.write_text(json.dumps(ALL_OFF), encoding="utf-8")
    _ = p_on.write_text(json.dumps(ALL_ON), encoding="utf-8")
    off_health = health(p_off)
    monkeypatch.setattr(server, "_HYGIENE_RT", cast(object, None))
    rt2 = _fn(server, "_hygiene_rt")()
    on_health = cast(Callable[..., object], getattr(rt2, "health_snapshot"))(p_on)
    assert on_health != off_health
    assert _any_true(on_health)
    assert not _any_true(off_health) or str(on_health) != str(off_health)


def test_file_sha256_delegates_to_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server = _load()
    fake = FakeRT(flags=FakeFlags(bounded_state_enabled=True))
    _install(server, monkeypatch, fake)
    target = tmp_path / "data.bin"
    _ = target.write_bytes(b"hello hygiene")
    digest = _fn(server, "_file_sha256")(target)
    assert digest == hashlib.sha256(b"hello hygiene").hexdigest()
    assert any(kind == "sha_put" for kind, _ in fake.calls)
    for key in list(fake.sha):
        fake.sha[key] = "deadbeef"
    assert _fn(server, "_file_sha256")(target) == "deadbeef"


def test_session_commit_invalidate_delegate_and_legacy_store(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load()
    fake = FakeRT(flags=FakeFlags(bounded_state_enabled=True))
    _install(server, monkeypatch, fake)
    store = cast("dict[object, object]", getattr(server, "_session_store"))
    commit = _fn(server, "_session_commit")
    invalidate = _fn(server, "_session_invalidate")
    candidates: list[tuple[str, ...]] = [("a",), ("a", "b"), ("m", "s", "t"), ("m", "s", "t", "c")]
    found: tuple[str, ...] | None = None
    for key in candidates:
        _ = commit(key, "cid-1")
        if key in store:
            found = key
            break
    assert any(kind == "commit" for kind, _ in fake.calls)
    assert found is not None, "no candidate sess_key accepted by _session_key_valid"
    _ = invalidate(found, "cid-1")
    assert found not in store
    assert any(kind == "invalidate" for kind, _ in fake.calls)


def _make_job(server: ModuleType, *, tools_count: int, ttfc_received: bool) -> object:
    job_cls = cast(type[object], getattr(server, "_Job"))
    job = object.__new__(job_cls)
    cancelled: list[str] = []
    setattr(job, "readers", 1)
    setattr(job, "result", None)
    setattr(job, "orphan", False)
    setattr(job, "cancelled", threading.Event())
    setattr(job, "cancel", lambda: cancelled.append("cancelled"))
    setattr(job, "tools_count", tools_count)
    setattr(job, "ttfc_received", ttfc_received)
    setattr(job, "pgid", 0)
    return job


def test_detach_baseline_and_post_ttfc(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load()
    registry_cls = cast(Callable[[], object], getattr(server, "JobRegistry"))
    _install(server, monkeypatch, FakeRT())
    registry = registry_cls()
    baseline_job = _make_job(server, tools_count=1, ttfc_received=False)
    _ = cast(Callable[..., object], getattr(registry, "detach"))(baseline_job, allow_orphan=True)
    assert getattr(baseline_job, "orphan") is True
    _install(server, monkeypatch, FakeRT(flags=FakeFlags(fast_client_gone_enabled=True, bounded_state_enabled=True)))
    fast_registry = registry_cls()
    pre_ttfc_job = _make_job(server, tools_count=1, ttfc_received=False)
    _ = cast(Callable[..., object], getattr(fast_registry, "detach"))(pre_ttfc_job, allow_orphan=True)
    assert getattr(pre_ttfc_job, "orphan") is False
    assert cast(threading.Event, getattr(pre_ttfc_job, "cancelled")).is_set()


def test_admission_shed_returns_overloaded_503(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load()
    fake = FakeRT(flags=FakeFlags(adaptive_admission_enabled=True), admit_next=False)
    _install(server, monkeypatch, fake)
    handler_cls = cast(type[object], getattr(server, "Handler"))
    handler = object.__new__(handler_cls)
    setattr(handler, "_log_reject", lambda *_a: None)
    setattr(handler, "_log_done", lambda *_a: None)
    out = cast("dict[str, object]", cast(Callable[..., object], getattr(handler, "_run_once_impl"))(
        {"model": "sonnet", "effort": "low", "tag": "t", "model_len": 6},
        lambda _v: None, lambda _v: None, lambda _v: None, lambda: True,
    ))
    assert out["state"] == "overloaded"
    err_body = cast("dict[str, object]", cast(Callable[..., object], getattr(handler_cls, "_error_body"))(out))
    assert err_body["code"] == 503
    assert err_body["type"] == "overloaded"

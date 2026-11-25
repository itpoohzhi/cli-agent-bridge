from __future__ import annotations

import ast
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.backend_routing_models import Transcript, TranscriptItem
from core.resident_identity import IdentityInputs, ResidentAuthError, ResidentIdentity, resolve_resident_identity
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_reaper import extract_handle_pgid, join_maintenance_thread
from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.resident_runtime import (
    PreDispatchResidentError,
    ResidentBridgeRuntime,
    ResidentCancelledError,
    ResidentStreamError,
    ResidentTurnOptions,
    ResourceLimitError,
)
from core.stdio_resident.types import SlotBinding

_SECRET = b"0123456789abcdef0123456789abcdef"


class _Logger:
    def __init__(self) -> None:
        self.warnings: list[tuple[object, ...]] = []
        self.exceptions: list[tuple[object, ...]] = []

    def warning(self, *args: object) -> None:
        self.warnings.append(args)

    def exception(self, *args: object) -> None:
        self.exceptions.append(args)


class _FakeHandle:
    def __init__(self, generation: int = 0, alive: bool = True) -> None:
        self.generation = generation
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


class _FakePool:
    def __init__(self, slots: list[Any], *, max_slots: int = 1) -> None:
        self.config = StdioPoolConfig(max_slots=max_slots, enabled=True)
        self._config = self.config
        self._slots = list(slots)
        self.released: list[tuple[str, bool, bool]] = []
        self.closed_idle: list[tuple[str, int]] = []

    def idle_binding(self, _key: Any) -> SlotBinding | None:
        return None

    def acquire(self, _key: Any, _argv: Any, _cwd: str, _env: Any, *, is_ephemeral: bool = False) -> Any:
        slot = self._slots.pop(0)
        slot.acquired_ephemeral = is_ephemeral
        return slot

    def release(self, slot_id: str, success: bool = True, cancel: bool = False, lease_id: str | None = None) -> bool:
        self.released.append((slot_id, success, cancel))
        return True

    def close_if_idle(self, slot_id: str, generation: int) -> bool:
        self.closed_idle.append((slot_id, generation))
        return True


def _env(*, ephemeral: bool = False, cid: str = "chat-1") -> ResidentTurnEnvelope:
    ident = ResidentIdentity("owner", cid, ephemeral, "", "t1", "", "", f"sess-{cid}", "eph" if ephemeral else "")
    tx = Transcript(items=(TranscriptItem("user", "hi", "u1"),), runnable=True)
    return ResidentTurnEnvelope(identity=ident, backend_id="b", model="m", effort="low", cwd_norm="/w", secret=_SECRET, rpc=tx, full_prompt="hi")


def _slot(sid: str = "s1", gen: int = 0, alive: bool = True) -> Any:
    return SimpleNamespace(slot_id=sid, lease_id="l1", handle=_FakeHandle(gen, alive), acquired_ephemeral=False)


def test_extract_handle_pgid_prefers_valid_group() -> None:
    assert extract_handle_pgid(SimpleNamespace(_pgid=41, pid=42)) == 41
    assert extract_handle_pgid(SimpleNamespace(_pgid=True, pid=42)) == 42
    assert extract_handle_pgid(SimpleNamespace(_pgid=-1, pid=0)) == 0


def test_join_maintenance_thread_ignores_current_thread() -> None:
    logger = _Logger()
    join_maintenance_thread(threading.current_thread(), 0.0, logger)
    done = threading.Event()
    other = threading.Thread(target=done.set)
    other.start()
    join_maintenance_thread(other, 1.0, logger)
    assert done.is_set() and not other.is_alive()
    assert logger.warnings == []


def test_runtime_errors_have_stable_public_codes() -> None:
    assert PreDispatchResidentError().code == "warm_slot_mismatch_after_retry"
    assert ResourceLimitError.code == "output_limit_exceeded"
    assert ResidentStreamError.code == "invalid_upstream_encoding"
    assert issubclass(ResidentCancelledError, RuntimeError)


def test_pre_write_dead_slot_raises_pre_dispatch() -> None:
    pool = _FakePool([_slot(alive=False)])
    rt = ResidentBridgeRuntime(pool, SimpleNamespace())
    with pytest.raises(PreDispatchResidentError, match="resident_process_not_alive"):
        list(rt.execute_turn(_env(), ResidentTurnOptions(argv_builder=lambda: ["cmd"])))
    assert pool.released == [("s1", True, True)]


def test_toctou_generation_mismatch_retries_and_fails_pre_dispatch() -> None:
    pool = _FakePool([_slot("s1", gen=1), _slot("s2", gen=2)])
    rt = ResidentBridgeRuntime(pool, SimpleNamespace())
    with pytest.raises(PreDispatchResidentError, match="warm_slot_mismatch_after_retry"):
        list(rt.execute_turn(_env(), ResidentTurnOptions(argv_builder=lambda: ["cmd"])))
    assert [entry[0] for entry in pool.released] == ["s1", "s2"]


def test_post_dispatch_error_cancels_and_does_not_retry() -> None:
    pool = _FakePool([_slot("s1", gen=0)])

    class _FailMidStream:
        def stream_turn(self, _h: Any, _e: Any) -> Any:
            yield DecodedChunk(text="ok", dispatched=True) if hasattr(DecodedChunk, "dispatched") else SimpleNamespace(text="ok", error=None, is_terminal=False, dispatched=True)
            raise ResidentStreamError("boom")

    rt = ResidentBridgeRuntime(pool, _FailMidStream())
    stream = rt.execute_turn(_env(), ResidentTurnOptions(argv_builder=lambda: ["cmd"]))
    assert next(stream).text == "ok"
    with pytest.raises(ResidentStreamError, match="boom"):
        next(stream)
    assert pool.released == [("s1", True, True)]


def test_consumer_close_before_terminal_cancels_slot() -> None:
    pool = _FakePool([_slot("s1", gen=0)])

    class _TwoChunks:
        def stream_turn(self, _h: Any, _e: Any) -> Any:
            yield DecodedChunk(text="first")
            yield DecodedChunk(text="second", is_terminal=True)

    rt = ResidentBridgeRuntime(pool, _TwoChunks())
    stream = rt.execute_turn(_env(), ResidentTurnOptions(argv_builder=lambda: ["cmd"]))
    assert next(stream).text == "first"
    stream.close()
    assert pool.released == [("s1", True, True)]


def test_post_release_commit_failure_closes_released_idle_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    slot = _slot("s1", gen=0)
    pool = _FakePool([slot])

    class _Done:
        def stream_turn(self, _h: Any, _e: Any) -> Any:
            yield SimpleNamespace(text="hi", error=None, is_terminal=False, dispatched=True)
            yield DecodedChunk(text="done", is_terminal=True)

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("commit exploded")

    rt = ResidentBridgeRuntime(pool, _Done())
    monkeypatch.setattr(rt._tracker, "commit", _boom)
    with pytest.raises(RuntimeError, match="commit exploded"):
        list(rt.execute_turn(_env(), ResidentTurnOptions(argv_builder=lambda: ["cmd"])))
    assert pool.closed_idle == [("s1", 0)]


def test_bounded_admission_cap_degrades_to_ephemeral_and_auth_blocks() -> None:
    held = _slot("s1", gen=0)
    pool = _FakePool([held], max_slots=1)

    class _Done:
        def stream_turn(self, _h: Any, _e: Any) -> Any:
            yield DecodedChunk(text="ok", is_terminal=True)

    rt = ResidentBridgeRuntime(pool, _Done())
    for idx in range(rt._cap):
        rt._session_locks[f"k-{idx}"] = SimpleNamespace(lock=threading.Lock(), waiters=1)
    list(rt.execute_turn(_env(cid="overflow"), ResidentTurnOptions(argv_builder=lambda: ["cmd"])))
    assert held.acquired_ephemeral is True

    with pytest.raises(ResidentAuthError):
        resolve_resident_identity(IdentityInputs(request={"session_id": "c1"}, headers=None, extra=None, secret=_SECRET, trusted_principal_hash="", require_auth=True))


def _slot_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name) and node.func.id == "SlotAffinityKey") or (isinstance(node.func, ast.Attribute) and node.func.attr == "SlotAffinityKey"):
                calls.append(node)
    return calls


def test_slots_require_env_digest_ast() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [p for d in (root / "core", root / "adapters") if d.exists() for p in d.rglob("*.py")]
    calls = [(p, c) for p in paths for c in _slot_calls(p)]
    assert calls
    for path, call in calls:
        kw = next((item for item in call.keywords if item.arg == "env_digest"), None)
        assert kw is not None, f"{path}:{call.lineno}: missing env_digest"
        assert not (isinstance(kw.value, ast.Constant) and kw.value.value == ""), f"{path}:{call.lineno}: empty env_digest"


def test_agy_timeout_boundaries() -> None:
    from adapters.stdio_drivers.agy_driver import AgyStreamJsonDriver
    from core.resident_identity import ResidentRequestError

    assert AgyStreamJsonDriver.validate_timeout({"print_timeout": 0}) == 30
    assert AgyStreamJsonDriver.validate_timeout({"print_timeout": 86400}) == 86400
    with pytest.raises(ResidentRequestError):
        _ = AgyStreamJsonDriver.validate_timeout({"print_timeout": 86400.1})


def test_wrap_emulate_tools_keepalive_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    import adapters.stdio_resident_runtime as rt_mod

    now = [0.0]
    calls: list[bool] = []
    monkeypatch.setattr(rt_mod.time, "monotonic", lambda: now[0])
    wrapped = rt_mod.wrap_emulate_tools_sse_writer(lambda *_a: True, True, 4096, lambda: None, lambda: calls.append(True) or True)
    assert wrapped is not None
    now[0] = 5.0
    assert wrapped("content", "a") is True and len(calls) == 0
    now[0] = 15.0
    assert wrapped("content", "b") is True and len(calls) == 1


def test_http_post_dispatch_native_inputs_and_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    from core import http_post_dispatch as hpd

    fake_adapter = SimpleNamespace(uses_resident_identity=False)
    monkeypatch.setattr(hpd, "_native_backend", lambda _r: fake_adapter)
    monkeypatch.setattr(hpd, "turn_ids_and_resident_ctx", lambda _r, _c, _e, adapter=None: bool(adapter and _r.request.get("valid")))
    handler = SimpleNamespace(_context_gate=lambda r, *_: (r, False), _forwarded_env=lambda *_: False if "bad_env" in _[0] else {})
    host = SimpleNamespace(_collect_images=lambda *_: (), ImageReject=RuntimeError)
    r_bad_env = SimpleNamespace(handler=handler, host=host, request={"valid": True, "extra_body": {"bad_env": 1}}, model_id="m", model={}, model_len=10)
    r_bad_id = SimpleNamespace(handler=handler, host=host, request={"valid": False, "extra_body": {}}, model_id="m", model={}, model_len=10)
    r_ok = SimpleNamespace(handler=handler, host=host, request={"valid": True, "extra_body": {}}, model_id="m", model={}, model_len=10)
    assert hpd._native_inputs(r_bad_env, {"effort": "low"}) is None
    assert hpd._native_inputs(r_bad_id, {"effort": "low"}) is None
    assert hpd._native_inputs(r_ok, {"effort": "low"}) is fake_adapter



def test_terminate_entries_logs_unexpected_only() -> None:
    from core.stdio_resident.process_io import StdioProcessTerminated
    from core.stdio_resident.process_reaper import terminate_entries

    logger = _Logger()
    e1 = SimpleNamespace(slot_id="s1", handle=SimpleNamespace(_pgid_dead=True))
    e2 = SimpleNamespace(slot_id="s2", handle=SimpleNamespace(_pgid_dead=True))

    def _term(entry: Any, _grace: float) -> None:
        raise StdioProcessTerminated("x") if entry.slot_id == "s1" else RuntimeError("boom")

    first_err, failed = terminate_entries([e1, e2], _term, 0.1, "test", logger)
    assert isinstance(first_err, StdioProcessTerminated)
    assert len(failed) == 2 and len(logger.exceptions) == 1


def test_runtime_output_byte_limit_and_keepalive(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.stdio_resident.resident_runtime as rt_mod

    now = [0.0]
    calls: list[bool] = []
    monkeypatch.setattr(rt_mod.time, "monotonic", lambda: now[0])
    assert rt_mod.ResidentBridgeRuntime._tick_keepalive(lambda: calls.append(True) or True, 0.0) == 0.0
    now[0] = 15.0
    assert rt_mod.ResidentBridgeRuntime._tick_keepalive(lambda: calls.append(True) or True, 0.0) == 15.0
    assert len(calls) == 1

    pool = _FakePool([_slot("s1"), _slot("s2")])

    class _ExactAndOver:
        def stream_turn(self, _h: Any, env: Any) -> Any:
            yield DecodedChunk(text="abcd", is_terminal=(env.full_prompt == "ok"))
            if env.full_prompt != "ok":
                yield DecodedChunk(text="e", is_terminal=True)

    rt = ResidentBridgeRuntime(pool, _ExactAndOver())
    ok_env = ResidentTurnEnvelope(identity=_env().identity, backend_id="b", model="m", effort="low", cwd_norm="/w", secret=_SECRET, rpc=_env().rpc, full_prompt="ok")
    list(rt.execute_turn(ok_env, ResidentTurnOptions(argv_builder=lambda: ["c"], max_output_bytes=4)))
    bad_env = ResidentTurnEnvelope(identity=_env().identity, backend_id="b", model="m", effort="low", cwd_norm="/w", secret=_SECRET, rpc=_env().rpc, full_prompt="over")
    with pytest.raises(ResourceLimitError, match="output_limit_exceeded"):
        list(rt.execute_turn(bad_env, ResidentTurnOptions(argv_builder=lambda: ["c"], max_output_bytes=4)))


def test_require_auth_allows_authenticated_ephemeral_and_blocks_missing_principal() -> None:
    held = _slot("s-eph")
    pool = _FakePool([held], max_slots=1)

    class _Done:
        def stream_turn(self, _h: Any, _e: Any) -> Any:
            yield DecodedChunk(text="ok", is_terminal=True)

    rt = ResidentBridgeRuntime(pool, _Done())
    auth_eph = _env(ephemeral=True, cid="")
    chunks = list(rt.execute_turn(auth_eph, ResidentTurnOptions(argv_builder=lambda: ["cmd"], require_auth=True)))
    assert [c.text for c in chunks] == ["ok"] and held.acquired_ephemeral is True

    unauth_id = ResidentIdentity("", "", True, "", "t1", "", "", "sess-none", "unauthenticated_ephemeral")
    unauth_env = ResidentTurnEnvelope(identity=unauth_id, backend_id="b", model="m", effort="low", cwd_norm="/w", secret=_SECRET, rpc=_env().rpc, full_prompt="hi")
    with pytest.raises(ResidentAuthError) as exc_info:
        list(rt.execute_turn(unauth_env, ResidentTurnOptions(argv_builder=lambda: ["cmd"], require_auth=True)))
    assert exc_info.value.http_status == 401 and exc_info.value.code == "auth_required"

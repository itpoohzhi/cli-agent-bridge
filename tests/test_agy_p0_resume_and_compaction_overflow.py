# pyright: reportPrivateUsage=false
# ruff: noqa: E402, I001
from __future__ import annotations

import ast
import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from threading import Lock
from typing import cast, final

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
for _p in (str(BRIDGE_DIR), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from resilience_wiring_support import load_server
except ImportError:
    from tests.resilience_wiring_support import load_server

from agy_runtime.history_compaction_domain import (
    DEFAULT_MIDDLE_PRUNED_MARKER,
    CompactionConfig,
    PromptBlock,
    compact_prompt_blocks,
    json_text_bytes,
    middle_prune_text,
)
from agy_runtime.history_overflow_policy import OverflowSpec, shrink_overflow_parts
from agy_runtime.hygiene_runtime import ManagedSqliteRoPool
from agy_runtime.midstream_resilience import finish_transcript_tail


@final
@dataclass(frozen=True, slots=True)
class _Plan:
    mode: str


@final
class _InnerPool:
    def __init__(self, should_raise: bool = False) -> None:
        self.release_calls: int = 0
        self.should_raise: bool = should_raise

    def query_rows(self, db_path: Path, sql: str) -> object:
        _ = (db_path, sql)
        return ()

    def run_ro(self, db_path: Path, fn: Callable[..., object], on_conn: object = None) -> object:
        _ = (db_path, fn, on_conn)
        return None

    def release_thread(self) -> None:
        self.release_calls += 1
        if self.should_raise:
            raise RuntimeError("pool")

    def close_all(self) -> None:
        return None


@final
class _Tail:
    def __init__(self, mode: str = "LIVE", cid: str = "cid", conn: object = None) -> None:
        self._finished: bool = False
        self._conn_lock: Lock = Lock()
        self._active_conn: object | None = conn
        self.plan: _Plan = _Plan(mode)
        self.probe_gen: int = 1
        self.selects_ok: int = 2
        self.failed: bool = False
        self._owned_cid: str = cid
        self.turn_id: str = "turn"


def _spec(
    limit_bytes: int,
    prune_fn: Callable[[str, int, str], str] = middle_prune_text,
    sep: str = "\n\n",
    size_fn: Callable[[str], int] = json_text_bytes,
) -> OverflowSpec:
    return OverflowSpec(limit_bytes, sep, DEFAULT_MIDDLE_PRUNED_MARKER, size_fn, prune_fn)


def _blk(index: int, role: str, body: str) -> PromptBlock:
    return PromptBlock(index=index, role=role, rendered=f"### {index}. {role}\n{body}")


def test_managed_pool_release_thread_delegates_and_none_is_safe() -> None:
    inner = _InnerPool()
    ManagedSqliteRoPool(inner, hygiene_enabled=False).release_thread()
    assert inner.release_calls == 1
    ManagedSqliteRoPool(None, hygiene_enabled=False).release_thread()


def test_real_transcript_finish_releases_pool_and_cid(monkeypatch: pytest.MonkeyPatch) -> None:
    agy_server = load_server()
    cid, turn_id = "resume-cid", "turn-1"
    owners: dict[str, str] = {cid: turn_id}
    released: list[tuple[str, str]] = []

    def release(value: str, owner: str) -> None:
        released.append((value, owner))
        if owners.get(value) == owner:
            _ = owners.pop(value)

    inner = _InnerPool()
    managed = ManagedSqliteRoPool(inner, hygiene_enabled=True)
    tail = object.__new__(cast(type[object], getattr(agy_server, "_TranscriptTail")))
    for k, v in (
        ("_finished", False), ("_conn_lock", Lock()), ("_active_conn", None),
        ("plan", _Plan("OFF")), ("_owned_cid", cid), ("turn_id", turn_id),
    ):
        setattr(tail, k, v)
    monkeypatch.setattr(agy_server, "_sqlite_ro_pool", lambda: managed)
    monkeypatch.setattr(agy_server, "_cid_release", release)
    cast(Callable[[], None], getattr(tail, "_finish"))()
    assert inner.release_calls == 1
    assert released == [(cid, turn_id)]
    assert cid not in owners


@pytest.mark.parametrize("failure", ["close", "pool", "breaker"])
def test_finish_releases_cid_on_every_failure_and_is_idempotent(failure: str) -> None:
    tail = _Tail(mode="LIVE", cid="cid", conn=object())
    pool = _InnerPool(should_raise=(failure == "pool"))
    released: list[tuple[str, str]] = []

    def close_fn(_conn: object) -> None:
        if failure == "close":
            raise RuntimeError("close")

    def breaker_fn(_g: int, _s: int, _f: bool) -> None:
        if failure == "breaker":
            raise RuntimeError("breaker")

    with pytest.raises(RuntimeError, match=failure):
        finish_transcript_tail(tail, close_fn, lambda: pool, breaker_fn, lambda c, t: released.append((c, t)))
    finish_transcript_tail(tail, close_fn, lambda: pool, breaker_fn, lambda c, t: released.append((c, t)))
    assert released == [("cid", "turn")]


def test_finish_optional_branches_shadow_off_empty_cid() -> None:
    closed: list[object] = []
    breaks: list[int] = []
    released: list[tuple[str, str]] = []
    finish_transcript_tail(
        _Tail(mode="SHADOW", cid="", conn=None),
        closed.append, lambda: None,
        lambda g, _s, _f: breaks.append(int(g)),
        lambda c, t: released.append((c, t)),
    )
    assert closed == []
    assert breaks == [1]
    assert released == []


def test_db3bc728_compact_domain_caps_digest_and_preserves_task() -> None:
    system_body = "AGENTS.md\n" + "A" * 38_000 + "\nmodel-notes.md\n" + "B" * 37_000
    task_body = "Задача: Grafana dashboard proxy-fleet\n" + "детали " * 250
    blocks: list[PromptBlock] = [_blk(0, "system", system_body), _blk(1, "user", task_body)]
    for turn in range(45):
        base = 2 + turn * 2
        blocks.append(_blk(base, "assistant", f"[tool call c{turn:02d}] read_metric_panel_series({turn}) " + "q" * 80))
        blocks.append(_blk(base + 1, "tool", f"[tool result c{turn:02d}] " + "x" * 1200))
    blocks.append(_blk(92, "user", "повторяю"))
    res = compact_prompt_blocks(blocks, CompactionConfig(limit_bytes=72_850))
    assert res.prompt_bytes <= 72_850
    assert json_text_bytes(res.prompt) == res.prompt_bytes
    assert task_body in res.prompt
    assert "### 92. user\nповторяю" in res.prompt
    assert DEFAULT_MIDDLE_PRUNED_MARKER in res.prompt
    assert "[сжатая история ходов" in res.prompt
    digest_seg = "[сжатая история ходов" + res.prompt.split("[сжатая история ходов", 1)[1].split("\n\n", 1)[0]
    assert json_text_bytes(digest_seg) <= 1024


def test_compact_domain_large_tail_tool_never_wipes_anchor_user_task() -> None:
    task_body = "TASK_CANARY_GRAFANA_PROXY_FLEET: проверь дашборд"
    blocks: list[PromptBlock] = [
        _blk(0, "system", "AGENTS.md\n" + "A" * 58_000),
        _blk(1, "user", task_body),
        _blk(2, "assistant", "[tool call m0] init()"),
        _blk(3, "tool", "[tool result m0] " + "m" * 4_000),
        _blk(4, "assistant", "[tool call t_big] dump_metrics()"),
        _blk(5, "tool", "[tool result t_big] " + "R" * 48_000 + " END_TOOL"),
    ]
    res = compact_prompt_blocks(blocks, CompactionConfig(limit_bytes=72_850))
    assert res.prompt_bytes <= 72_850
    assert task_body in res.prompt
    assert "[tool call t_big]" in res.prompt
    assert "[tool result t_big]" in res.prompt
    assert DEFAULT_MIDDLE_PRUNED_MARKER in res.prompt


def test_overflow_short_circuit_single_user_and_multi_tool_order() -> None:
    size_inputs: list[str] = []
    prune_calls: list[str] = []

    def spy_size(s: str) -> int:
        size_inputs.append(s)
        return json_text_bytes(s)

    def spy_prune(text: str, lim: int, marker: str) -> str:
        prune_calls.append(text)
        return middle_prune_text(text, lim, marker)

    assert shrink_overflow_parts([("user", "short")], _spec(100, spy_prune, size_fn=spy_size)) == "short"
    assert len(size_inputs) == 1
    assert prune_calls == []

    p_user = shrink_overflow_parts([("user", "U" * 5_000)], _spec(1_000, spy_prune))
    assert json_text_bytes(p_user) <= 1_000
    assert len(prune_calls) == 1

    prune_calls.clear()
    t_small = "[tool small] " + "m" * 400
    t_big = "[tool big] " + "R" * 8_000 + " END"
    p2 = shrink_overflow_parts([("system", "S" * 1_000), ("tool", t_small), ("tool", t_big)], _spec(4_000, spy_prune))
    assert json_text_bytes(p2) <= 4_000
    assert t_small in p2
    assert len(p2) > 3_000
    assert prune_calls == [t_big]


def test_overflow_empty_skip_zero_avail_and_digest() -> None:
    size_inputs: list[str] = []

    def spy_size(s: str) -> int:
        size_inputs.append(s)
        return json_text_bytes(s)

    _ = shrink_overflow_parts([("system", "S" * 50), ("system", "S" * 50), ("tool", "")], _spec(50, size_fn=spy_size))
    assert "" not in size_inputs

    p_zero = shrink_overflow_parts([("system", "A" * 9), ("tool", "B" * 300)], _spec(10, sep=" "))
    assert p_zero == "A" * 9

    p_drop = shrink_overflow_parts([("system", "S" * 100), ("digest", "DIGEST_DROP_" + "d" * 300), ("user", "U" * 100)], _spec(230))
    assert json_text_bytes(p_drop) <= 230
    assert "DIGEST_DROP_" not in p_drop

    p_keep = shrink_overflow_parts([("system", "S" * 100), ("digest", "DIGEST_KEEP_" + "d" * 400 + "-END"), ("user", "U" * 100)], _spec(350))
    assert json_text_bytes(p_keep) <= 350
    assert "DIGEST_KEEP_" in p_keep


def test_overflow_floor_spec_immutability_and_tiny_limits() -> None:
    calls: list[str] = []

    def spy_prune(text: str, lim: int, marker: str) -> str:
        calls.append(text)
        return middle_prune_text(text, lim, marker)

    small_sys, big_sys = "SYS_SMALL", "SYS_BIG_" + "S" * 600
    p_floor = shrink_overflow_parts(
        [("system", small_sys), ("system", big_sys), ("user", "U_HEAD_" + "X" * 4_000 + "_U_TAIL")],
        _spec(1_200, spy_prune),
    )
    assert json_text_bytes(p_floor) <= 1_200
    assert small_sys in p_floor
    assert small_sys not in calls
    assert big_sys in calls
    assert shrink_overflow_parts([("user", "X" * 500)], _spec(10, lambda t, _l, _m: t)) == ""
    assert shrink_overflow_parts([("user", "X" * 50)], _spec(0, lambda _t, _l, _m: "Z")) == ""
    assert shrink_overflow_parts([("user", "X" * 50)], _spec(-5)) == ""
    assert shrink_overflow_parts([], _spec(0)) == ""
    spec = _spec(10)
    assert not hasattr(spec, "__dict__")
    with pytest.raises(FrozenInstanceError):
        spec.limit_bytes = 20  # type: ignore[misc]


def test_policy_module_is_pure_and_bounded() -> None:
    path = BRIDGE_DIR / "agy_runtime" / "history_overflow_policy.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {"__future__", "collections.abc", "dataclasses"}
    assert len(source.splitlines()) <= 200
    for node in tree.body:
        assert not isinstance(node, ast.Import)
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            assert not isinstance(node.value, (ast.List, ast.Dict, ast.Set))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert (node.end_lineno or 0) - node.lineno + 1 <= 40
            assert len(node.args.posonlyargs) + len(node.args.args) + len(node.args.kwonlyargs) <= 5

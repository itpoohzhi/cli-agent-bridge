"""Unit-тесты модуля отложенного explicit-коммита (explicit_turn_commit, AD-001 / BUG-B1)."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
for _p in (str(ROOT), str(BRIDGE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agy_runtime.explicit_turn_commit import (  # noqa: E402
    abort_explicit_turn_safe,
    build_explicit_commit_out,
    finalize_deferred_explicit_turn,
)

_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_CID_1 = "11111111-1111-4111-8111-111111111111"


class _ToolTurn:
    def __init__(self, content: str = "", calls: list[dict[str, Any]] | None = None, error: Any = None, ok: bool = True) -> None:
        self.content, self.calls, self.error, self.ok = content, list(calls or []), error, ok


class _State:
    def __init__(self) -> None:
        self.handled, self.finalized = True, False


class _Adapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def finalize_turn(self, state: _State, out: dict[str, Any], commit_act: str, cid_re: re.Pattern[str]) -> bool:
        state.finalized = True
        self.calls.append((commit_act, str(out.get("text")), dict(out)))
        return commit_act == "commit"

    def release_if_unfinalized(self, state: _State, *, post_spawn: bool = True) -> None:
        state.finalized = True
        self.calls.append(("release", "", {"post_spawn": post_spawn}))


def _mk_out(text: str = "", tool_calls: list[dict[str, Any]] | None = None, cid: str = _CID_1) -> dict[str, Any]:
    out: dict[str, Any] = {"conversation_id": cid, "text": text}
    if tool_calls is not None:
        out["tool_calls"] = tool_calls
    return out

def test_build_out_with_tool_turn_no_strip_and_empty_calls_removed() -> None:
    tt = _ToolTurn(content="  final  text  ")
    src = _mk_out(text="  RAW thinking ", tool_calls=[{"id": "c1"}])
    snapshot = dict(src)
    built = build_explicit_commit_out(src, tt)
    assert built["text"] == "  final  text  "
    assert "tool_calls" not in built
    assert built["conversation_id"] == _CID_1
    assert src == snapshot


def test_build_out_with_tool_turn_calls_present() -> None:
    calls = [{"id": "call_1", "type": "function", "function": {"name": "z_tool", "arguments": "{}"}}]
    tt = _ToolTurn(content="done", calls=calls)
    built = build_explicit_commit_out(_mk_out(text="raw"), tt)
    assert built["tool_calls"] == calls
    assert built["text"] == "done"


def test_build_out_plain_preserves_exact_whitespace_and_input_not_mutated() -> None:
    src = _mk_out(text="  keep   me\n")
    snapshot = dict(src)
    built = build_explicit_commit_out(src, None)
    assert built["text"] == "  keep   me\n"
    assert src == snapshot
    assert built is not src

def test_finalize_commit_uses_cleaned_tool_turn_content() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="RAW thinking ...", tool_calls=[]), tool_turn=_ToolTurn(content="final text"), cid_re=_CID_RE)
    assert ok is True
    assert len(ad.calls) == 1
    act, text, out = ad.calls[0]
    assert act == "commit" and text == "final text"
    assert "tool_calls" not in out
    assert st.finalized is True


def test_finalize_commit_keeps_buffered_tail_after_finish() -> None:
    """Сырой text содержит буферизованный хвост после finish() — клиенту отдаём только очищенное."""
    ad, st = _Adapter(), _State()
    raw_out = _mk_out(text="visible\n\x1b[0m tail-buffer-after-finish", tool_calls=[{"id": "c1"}])
    ok = finalize_deferred_explicit_turn(ad, st, raw_out, tool_turn=_ToolTurn(content="visible\n"), cid_re=_CID_RE)
    assert ok is True
    _, text, _ = ad.calls[0]
    assert text == "visible\n"
    assert "tail-buffer" not in text


def test_finalize_err_aborts_and_never_commits_slot() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="x"), tool_turn=_ToolTurn(content="x"), err=RuntimeError("LiveParserError"), cid_re=_CID_RE)
    assert ok is False
    assert [c[0] for c in ad.calls] == ["abort"]
    assert st.finalized is True


def test_finalize_tool_turn_error_aborts() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="x"), tool_turn=_ToolTurn(content="x", error=ValueError("boom")), cid_re=_CID_RE)
    assert ok is False and ad.calls[0][0] == "abort"


def test_finalize_tool_turn_not_ok_aborts() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="x"), tool_turn=_ToolTurn(content="x", ok=False), cid_re=_CID_RE)
    assert ok is False and ad.calls[0][0] == "abort"


def test_finalize_non_commit_act_aborts() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="x"), tool_turn=_ToolTurn(content="x"), commit_act="abort", cid_re=_CID_RE)
    assert ok is False and ad.calls[0][0] == "abort"


def test_finalize_cid_re_none_aborts_without_calling_finalize_turn() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="ok"), tool_turn=_ToolTurn(content="ok"), commit_act="commit", cid_re=None)
    assert ok is False
    assert st.finalized is True
    assert ad.calls == [("release", "", {"post_spawn": True})]


def test_finalize_str_err_aborted_aborts_and_empty_dict_commits() -> None:
    ad_err, st_err = _Adapter(), _State()
    assert finalize_deferred_explicit_turn(ad_err, st_err, _mk_out(text="x"), err="aborted", cid_re=_CID_RE) is False
    assert [c[0] for c in ad_err.calls] == ["abort"]
    ad_empty, st_empty = _Adapter(), _State()
    assert finalize_deferred_explicit_turn(ad_empty, st_empty, _mk_out(text="ok"), err={}, cid_re=_CID_RE) is True
    assert [c[0] for c in ad_empty.calls] == ["commit"]


def test_finalize_plain_without_tool_turn_preserves_exact_whitespace() -> None:
    ad, st = _Adapter(), _State()
    ok = finalize_deferred_explicit_turn(ad, st, _mk_out(text="  exact  ws \n"), cid_re=_CID_RE)
    assert ok is True and ad.calls[0][1] == "  exact  ws \n"


def test_finalize_idempotent_second_call_returns_false() -> None:
    ad, st = _Adapter(), _State()
    assert finalize_deferred_explicit_turn(ad, st, _mk_out(text="a"), cid_re=_CID_RE) is True
    assert finalize_deferred_explicit_turn(ad, st, _mk_out(text="b"), cid_re=_CID_RE) is False
    assert len(ad.calls) == 1


def test_finalize_guards_none_and_unhandled() -> None:
    st = _State()
    ad = _Adapter()
    assert finalize_deferred_explicit_turn(None, st, _mk_out(), cid_re=_CID_RE) is False
    assert finalize_deferred_explicit_turn(ad, None, _mk_out(), cid_re=_CID_RE) is False
    st_unhandled = _State()
    st_unhandled.handled = False
    assert finalize_deferred_explicit_turn(ad, st_unhandled, _mk_out(), cid_re=_CID_RE) is False
    assert ad.calls == []


def test_abort_safe_releases_once_with_post_spawn() -> None:
    ad, st = _Adapter(), _State()
    abort_explicit_turn_safe(ad, st, post_spawn=True)
    assert st.finalized is True and ad.calls == [("release", "", {"post_spawn": True})]
    abort_explicit_turn_safe(ad, st)
    assert len(ad.calls) == 1


def test_abort_safe_suppresses_errors_and_guards() -> None:
    class _Boom:
        def release_if_unfinalized(self, *_a: object, **_k: object) -> None:
            raise RuntimeError("no lease")

    abort_explicit_turn_safe(_Boom(), _State())
    abort_explicit_turn_safe(None, None)
    ad, st = _Adapter(), _State()
    st.finalized = True
    abort_explicit_turn_safe(ad, st)
    assert ad.calls == []

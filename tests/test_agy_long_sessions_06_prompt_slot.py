"""Unit-тесты для core/prompt_budget_policy.py и core/slot_acquire.py (W6, D1/D3)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.prompt_budget_policy import (  # noqa: E402
    LazyPromptMaterializer,
    compute_prompt_budget,
    resolve_ctx_prompt,
)
from core.slot_acquire import SlotWaitOptions, acquire_slot_timed  # noqa: E402


def test_prompt_budget_policy_is_vendor_agnostic_and_lazy() -> None:
    text = (_ROOT / "core/prompt_budget_policy.py").read_text(encoding="utf-8")
    assert "98304" not in text
    assert "agy" not in text.lower()

    assert compute_prompt_budget(max_cap_bytes=98304, env_cap_bytes=None, floor_bytes=16384, reserve_bytes=4096) == 94208
    assert compute_prompt_budget(max_cap_bytes=98304, env_cap_bytes=200000, floor_bytes=16384, reserve_bytes=0) == 98304
    assert compute_prompt_budget(max_cap_bytes=98304, env_cap_bytes=4096, floor_bytes=16384, reserve_bytes=1000) == 16384

    calls = 0

    def _build() -> str:
        nonlocal calls
        calls += 1
        return "materialized-prompt"

    mat = LazyPromptMaterializer(_build)
    assert mat.materialized is False
    ctx: dict[str, object] = {"full_prompt": mat, "plain": "hello"}
    assert resolve_ctx_prompt(ctx, "plain") == "hello"
    assert resolve_ctx_prompt(ctx, "missing") == ""
    assert calls == 0
    assert resolve_ctx_prompt(ctx, "full_prompt") == "materialized-prompt"
    assert mat.materialized is True and ctx["full_prompt"] == "materialized-prompt"
    assert resolve_ctx_prompt(ctx, "full_prompt") == "materialized-prompt"
    assert calls == 1


def test_acquire_slot_timed_no_keepalive_at_t0_and_throttled() -> None:
    now = [0.0]
    ka_times: list[float] = []
    attempts = [0]

    class _Slots:
        def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
            if not blocking:
                return False
            attempts[0] += 1
            now[0] += 5.0
            return attempts[0] >= 4

    opts = SlotWaitOptions(
        poll_s=0.1,
        keepalive=lambda: (ka_times.append(now[0]) or True),
        keepalive_interval_s=15.0,
        clock=lambda: now[0],
    )
    outcome, wait_ms = acquire_slot_timed(_Slots(), 30.0, lambda: False, opts)
    assert outcome == "ok"
    assert wait_ms == 20000
    # НИКОГДА на t=0, ровно один вызов при t=15.0
    assert ka_times == [15.0]


def test_acquire_slot_timed_timeout_client_gone_and_nonpositive_interval() -> None:
    class _BusySlots:
        def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
            return False

    class _FreeSlots:
        def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
            return True

    assert acquire_slot_timed(_FreeSlots(), 5.0, lambda: False) == ("ok", 0)
    assert acquire_slot_timed(_FreeSlots(), 5.0, lambda: True) == ("client_gone", 0)

    now = [0.0]
    ka_called = [0]

    def _tick() -> float:
        now[0] += 1.0
        return now[0]

    opts_zero = SlotWaitOptions(
        poll_s=0.1,
        keepalive=lambda: (ka_called.__setitem__(0, ka_called[0] + 1) or True),
        keepalive_interval_s=0.0,
        clock=_tick,
    )
    out_to, _ = acquire_slot_timed(_BusySlots(), 2.0, lambda: False, opts_zero)
    assert out_to == "timeout"
    assert ka_called[0] == 0

    # keepalive вернул False -> client_gone
    now2 = [0.0]

    def _tick2() -> float:
        now2[0] += 20.0
        return now2[0]

    opts_dead = SlotWaitOptions(poll_s=0.1, keepalive=lambda: False, keepalive_interval_s=15.0, clock=_tick2)
    out_dead, _ = acquire_slot_timed(_BusySlots(), 60.0, lambda: False, opts_dead)
    assert out_dead == "client_gone"

"""Hub P1.2 client-disconnect cancel, OPEN-16 resident wiring, and confirmed-dead slot gate (W11)."""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.p12_flag_and_params import (
    FLAG_HUB_NONDETACHED_CANCEL,
    FLAG_HUB_RESIDENT_WIRING,
    FLAG_HUB_TURN_MODE_PROPAGATION,
    CleanupParamSnapshot,
    SourcedParam,
    ValidatedCleanupParams,
    validate_cleanup_params,
)
from core.pgid_cleanup_driver import (
    CachedDynamicFlagReader,
    PosixProcProbe,
    ProcProbePort,
    darwin_probe_live_pid,
)
from core.pgid_cleanup_policy import CleanupKey, GroupProbeStatus
from core.pgid_reaper import AlertCallback, BoundedPgidReaper, ReleaseCallback
from core.turn_mode_cancel_policy import (
    INTERNAL_TURN_MODE_HEADER,
    CancelDecision,
    ClientDisconnectContext,
    SlotReleaseDecision,
    TurnMode,
    build_internal_turn_mode_header,
    decide_client_disconnect,
    decide_slot_release,
    resolve_turn_mode,
    strip_external_turn_mode_headers,
)


def sourced_hub_cleanup_params(
    *,
    term_grace_s: float = 2.0,
    poll_interval_s: float = 0.05,
    leader_wait_s: float = 2.0,
) -> CleanupParamSnapshot:
    """Sourced hub PGID teardown timings from TurnSessionManager._terminate_pgid (2.0s/0.05s)."""
    src = "core/turn_session_manager.py:TurnSessionManager._terminate_pgid"
    return CleanupParamSnapshot(
        service="cli-agent-bridge-hub",
        term_grace_s=SourcedParam(term_grace_s, f"{src}.grace_s"),
        poll_interval_s=SourcedParam(poll_interval_s, f"{src}.poll_s"),
        leader_wait_s=SourcedParam(leader_wait_s, f"{src}.leader_wait_s"),
    )


def strip_ingress_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Unconditionally strip external spoofed X-Bridge-Internal-Turn-Mode (regardless of flag #6)."""
    return strip_external_turn_mode_headers(headers)


def strip_http_message_turn_mode(headers: Any) -> bool:
    """In-place case-insensitive strip of X-Bridge-Internal-Turn-Mode on http.client.HTTPMessage."""
    if headers is None or not hasattr(headers, "keys"):
        return False
    removed = False
    target = INTERNAL_TURN_MODE_HEADER.lower()
    for key in list(headers.keys()):
        if str(key).strip().lower() == target:
            try:
                del headers[key]
                removed = True
            except Exception:
                pass
    return removed


def extract_resident_handle_pgid(handle: Any) -> int:
    """Best-effort extract live process PGID from a resident SlotHandle without throwing."""
    for attr in ("pgid", "pid"):
        val = getattr(handle, attr, None)
        if isinstance(val, int) and val > 1:
            return val
    proc = getattr(handle, "proc", None) or getattr(handle, "_proc", None)
    pid = getattr(proc, "pid", None) if proc is not None else None
    return int(pid) if isinstance(pid, int) and pid > 1 else 0


def bind_resident_slot_pgid(handle: Any, turn_ctx: Mapping[str, Any] | None) -> int:
    """OPEN-16 seam called by ResidentBridgeRuntime after slot acquisition (keeps LOC<=300)."""
    if not isinstance(turn_ctx, Mapping):
        return 0
    if not get_hub_p12_seam().resident_wiring_enabled():
        return 0
    reg = turn_ctx.get("_register_pgid") or turn_ctx.get("register_pgid")
    if not callable(reg):
        return 0
    pgid = extract_resident_handle_pgid(handle)
    if pgid > 1:
        try:
            reg(pgid)
        except Exception:
            pass
    return pgid


@dataclass(frozen=True)
class ResidentCancelHandle:
    """OPEN-16 explicit cancel & PGID registration handle threaded into ResidentBridgeRuntime."""

    cancel_event: threading.Event | None = None
    register_pgid: Callable[[int], None] | None = None
    wired: bool = False

    def register_slot_handle(self, handle: Any, *, enabled: bool) -> int:
        if not enabled or self.register_pgid is None:
            return 0
        pgid = extract_resident_handle_pgid(handle)
        if pgid > 1:
            try:
                self.register_pgid(pgid)
            except Exception:
                pass
        return pgid

    def is_cancelled(self) -> bool:
        return bool(self.cancel_event is not None and self.cancel_event.is_set())


class HubP12CancelSeam:
    """Hub coordinator for flags #4/#5/#6, TurnMode resolution, resident wiring, and PGID gate."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        params_snapshot: CleanupParamSnapshot | None = None,
        probe: ProcProbePort | None = None,
        on_alert: AlertCallback | None = None,
    ) -> None:
        self._params_snap = params_snapshot if params_snapshot is not None else sourced_hub_cleanup_params()
        self._flags = CachedDynamicFlagReader(config_path, env_path_var="BRIDGE_DYNAMIC_FLAGS_PATH")
        self._probe: ProcProbePort = probe or PosixProcProbe()
        self._on_alert = on_alert
        self._epoch_seq = itertools.count(1)
        self._lock = threading.Lock()
        self._reaper: BoundedPgidReaper | None = None

    def nondetached_cancel_enabled(self) -> bool:
        return self._flags.resolve(FLAG_HUB_NONDETACHED_CANCEL, None).enabled

    def resident_wiring_enabled(self) -> bool:
        return self._flags.resolve(FLAG_HUB_RESIDENT_WIRING, None).enabled

    def turn_mode_propagation_enabled(self) -> bool:
        return self._flags.resolve(FLAG_HUB_TURN_MODE_PROPAGATION, None).enabled

    def _get_reaper(self) -> BoundedPgidReaper:
        with self._lock:
            if self._reaper is None:
                validated: ValidatedCleanupParams = validate_cleanup_params(self._params_snap)
                self._reaper = BoundedPgidReaper(validated, probe=self._probe, on_alert=self._on_alert)
            return self._reaper

    def resolve_mode_for_ctx(self, ctx: Mapping[str, Any] | None) -> TurnMode:
        if ctx is None:
            return TurnMode.UNKNOWN
        existing = ctx.get("turn_mode")
        if isinstance(existing, TurnMode):
            return existing
        if "detach_on_disconnect" in ctx:
            return resolve_turn_mode(bool(ctx.get("detach_on_disconnect")))
        return TurnMode.UNKNOWN

    def propagation_header(self, mode: TurnMode) -> tuple[str, str] | None:
        return build_internal_turn_mode_header(mode, self.turn_mode_propagation_enabled())

    def build_resident_cancel_handle(
        self,
        cancel_event: threading.Event | None,
        register_pgid: Callable[[int], None] | None,
    ) -> ResidentCancelHandle:
        wired = self.resident_wiring_enabled() and cancel_event is not None
        return ResidentCancelHandle(
            cancel_event=cancel_event,
            register_pgid=register_pgid if wired else None,
            wired=wired,
        )

    def on_client_disconnect(
        self,
        managed_turn: Any,
        turn_manager: Any,
        mode: TurnMode,
        *,
        is_resident: bool = False,
        cancel_wired: bool = True,
    ) -> CancelDecision:
        """Apply pure 3x3 disconnect policy against TurnSessionManager."""
        ctx = ClientDisconnectContext(
            mode=mode,
            flag_nondetached_cancel=self.nondetached_cancel_enabled(),
            flag_resident_wiring=self.resident_wiring_enabled(),
            flag_turn_mode_propagation=self.turn_mode_propagation_enabled(),
            is_resident=is_resident,
            cancel_wired=cancel_wired,
        )
        decision = decide_client_disconnect(ctx)
        if managed_turn is None or turn_manager is None:
            return decision
        if decision is CancelDecision.MARK_DETACHED:
            turn_manager.mark_detached(managed_turn.turn_id)
        elif decision is CancelDecision.CANCEL_NONDETACHED:
            turn_manager.cancel_turn(managed_turn.turn_id, reason="client_disconnected")
        return decision

    def gate_slot_release(
        self,
        turn_id: str,
        pgid: int | None,
        release_fn: ReleaseCallback,
        reap_leader: Callable[[], int | None] | None = None,
    ) -> SlotReleaseDecision:
        """Gate slot release on confirmed-dead PGID ONLY when flag #4 on AND pgid registered."""
        pgid_ok = isinstance(pgid, int) and pgid > 1
        dead = (self._probe.probe_group(pgid) is GroupProbeStatus.GONE_ESRCH) if pgid_ok else True
        decision = decide_slot_release(self.nondetached_cancel_enabled(), pgid_ok, dead)
        if decision is SlotReleaseDecision.RELEASE_IMMEDIATE:
            release_fn()
            return decision
        assert pgid is not None
        ident = darwin_probe_live_pid(pgid)
        key = CleanupKey(
            turn_id=turn_id or f"hub-{pgid}",
            attempt_epoch=next(self._epoch_seq),
            pgid=pgid,
            leader_pid=pgid,
            leader_start_time_us=ident.start_time_us if ident is not None else 0,
        )
        self._get_reaper().register_and_cancel(key, release_fn, reap_leader=reap_leader)
        return decision

    def shutdown(self, timeout_s: float = 1.0) -> None:
        if self._reaper is not None:
            self._reaper.shutdown(timeout_s=timeout_s)


_HUB_P12_LOCK = threading.Lock()
_HUB_P12_SEAM: HubP12CancelSeam | None = None


def get_hub_p12_seam() -> HubP12CancelSeam:
    global _HUB_P12_SEAM
    if (s := _HUB_P12_SEAM) is not None:
        return s
    with _HUB_P12_LOCK:
        if _HUB_P12_SEAM is None:
            _HUB_P12_SEAM = HubP12CancelSeam()
        return _HUB_P12_SEAM


def reset_hub_p12_seam_for_tests() -> None:
    global _HUB_P12_SEAM
    with _HUB_P12_LOCK:
        if _HUB_P12_SEAM is not None:
            _HUB_P12_SEAM.shutdown()
        _HUB_P12_SEAM = None

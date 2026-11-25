"""Pure route circuit-breaker policy: auth taxonomy and recordability rules."""
from __future__ import annotations

from core.route_cb_config import (  # noqa: F401
    PROVIDER_AUTH_MARKERS,
    ROUTE_LOCAL_MARKERS,
    FailureOutcome,
    RouteCBConfig,
    RouteProbeLease,
    RouteTupleKey,
    _DEFAULT_COOLDOWN_S,
    _DEFAULT_THRESHOLD,
    _DEFAULT_WINDOW_S,
    _LEGACY_COOLDOWN_S,
    _LEGACY_THRESHOLD,
    _MAX_COOLDOWN_S,
    _MIN_COOLDOWN_S,
    _ProviderState,
    _TupleState,
    _UNPROVEN_DEQUE_MAX,
    _parse_float,
    _parse_int,
    is_route_cb_enabled,
    load_route_cb_config,
    resolve_provider,
)
from core.route_cb_legacy import (  # noqa: F401
    _with_retry_after,
    apply_quota_429,
    legacy_failure_action,
    refusal_detail,
)


def is_client_gone(error: BaseException | None = None, status: int | None = None, reason: str = "") -> bool:
    """Detect client disconnect, cancellation, BrokenPipeError, or HTTP 499."""
    if status == 499 or reason.lower() in {"client_gone", "client_disconnected"}:
        return True
    if error is None:
        return False
    return isinstance(error, BrokenPipeError) or type(error).__name__ in {"ClientDisconnect", "CancelledError", "BrokenPipeError"}


def classify_auth_failure(status: int, detail: str = "") -> str:
    """Classify 401/402/403 strictly in priority order: route_local -> provider_wide -> unproven."""
    text = detail.lower()
    if status == 403 and any(marker in text for marker in ROUTE_LOCAL_MARKERS):
        return "route_local"
    if status in (401, 402, 403) and any(marker in text for marker in PROVIDER_AUTH_MARKERS):
        return "provider_wide"
    return "unproven" if status in (401, 402, 403) else "none"


def is_recordable_failure(status: int | None = None, error: BaseException | None = None, reason: str = "") -> bool:
    """Return True only for record_fail-class outcomes; excludes 400/404/422/client_gone/499."""
    if is_client_gone(error, status, reason):
        return False
    if status is not None:
        return status == 429 or status in (401, 402, 403) or 500 <= status <= 599
    low = reason.lower()
    if low == "broken_stream" or "timeout" in low or low == "network_error":
        return True
    if error is not None:
        return isinstance(error, (TimeoutError, ConnectionError, OSError)) or type(error).__name__ in {"PreSendTransientError", "BrokenStreamError"}
    return False

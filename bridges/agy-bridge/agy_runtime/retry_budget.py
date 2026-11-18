"""Request-budget and cancellation checks for retry attempts."""


def should_allow_retry_attempt(
    *, attempt: int, cancelled: bool, can_start: bool
) -> tuple[bool, str]:
    if cancelled:
        return False, "client_gone"
    if not can_start:
        return False, "request_budget_exhausted"
    return True, ""

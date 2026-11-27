"""Pure Zero-Canon policy, effort matrix, attestation, and error taxonomy for Codex v2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, cast

ZERO_CANON_PROFILE: Final[str] = "zero-canon"
STANDARD_PROFILE: Final[str] = "standard"
CODEX_BACKEND_ID: Final[str] = "codex"
CODEX_V2_ROUTE_ID: Final[str] = "codex-app-server-v2"
EXECUTION_KIND_EPHEMERAL: Final[str] = "ephemeral"
ATTESTATION_HEADER: Final[str] = "X-Zero-Canon-Attestation"
ATTESTATION_PHASES: Final[frozenset[str]] = frozenset({"admitted", "completed"})
ERR_TOOL_EVENT_FORBIDDEN: Final[str] = "zero_canon_tool_event_forbidden"

CODEX_EFFORT_MATRIX: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType({
    "gpt-6.1-sol": ("low", "medium", "high", "xhigh", "max"),
    "gpt-6.2-sol": ("low", "medium", "high", "xhigh", "max"),
    "gpt-6.1-terra": ("low", "medium", "high"),
})
CODEX_DEFAULT_EFFORTS: Final[Mapping[str, str]] = MappingProxyType({"gpt-6.1-sol": "high", "gpt-6.2-sol": "high", "gpt-6.1-terra": "high"})
STRICT_STRIPPED_REQUEST_KEYS: Final[frozenset[str]] = frozenset(
    "tools tool_choice emulate_tools functions function_call parallel_tool_calls".split()
)
FORBIDDEN_TOOL_METHODS: Final[frozenset[str]] = frozenset(
    "item/commandExecution/requestApproval item/commandExecution/outputDelta "
    "item/commandExecution/terminalInteraction item/fileChange/requestApproval "
    "item/fileChange/outputDelta item/fileChange/patchUpdated item/mcpToolCall/progress "
    "item/permissions/requestApproval item/tool/call item/tool/requestUserInput "
    "command/exec/outputDelta mcpServer/elicitation/request applyPatchApproval execCommandApproval".split()
)
FORBIDDEN_TOOL_ITEM_TYPES: Final[frozenset[str]] = frozenset(
    "commandExecution fileChange mcpToolCall dynamicToolCall collabAgentToolCall "
    "webSearch functionCallOutput imageView imageGeneration tool_call toolCall function_call functionCall".split()
)
_TIMEOUT_MAP: Final[Mapping[str, str]] = MappingProxyType(
    {"first_progress": "first_progress_timeout", "idle": "idle_timeout", "safety_cap": "safety_cap_timeout"}
)
# error_class -> (http_status, scope, retryable, failover_pre_byte, cancel_pgid, fail_closed)
ERROR_TAXONOMY: Final[Mapping[str, tuple[int, str, bool, bool, bool, bool]]] = MappingProxyType({
    "credential_unavailable": (503, "credential", False, True, False, False),
    "rate_limit_transient": (429, "credential", True, True, False, False),
    "quota_exhausted": (429, "credential", False, True, False, False),
    "rate_limit_unknown": (429, "credential", False, False, False, True),
    "resident_protocol_failed": (502, "route", False, True, False, False),
    "upstream_incomplete_stream": (502, "route", False, True, False, False),
    "first_progress_timeout": (504, "turn", False, True, True, False),
    "idle_timeout": (504, "turn", False, True, True, False),
    "safety_cap_timeout": (504, "turn", False, True, True, False),
    "turn_timeout": (504, "turn", False, True, True, False),
    "bridge_draining": (503, "route", True, True, False, False),
    ERR_TOOL_EVENT_FORBIDDEN: (502, "policy", False, False, True, True),
})
_QUOTA_KEYS: Final[tuple[str, ...]] = ("insufficient_quota", "quota", "usage limit", "limit reached", "billing")
_TRANSIENT_KEYS: Final[tuple[str, ...]] = ("retry-after", "retry_after", "too many requests", "temporarily", "overloaded")
_INCOMPLETE_KEYS: Final[tuple[str, ...]] = ("eof", "empty done", "missing terminal", "incomplete stream", "unexpected end")


class CodexZeroCanonPolicyError(ValueError):
    """Typed fail-closed policy violation with machine error code and HTTP status."""

    def __init__(self, code: str, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.code, self.http_status, self.message = code, http_status, message


def _err(code: str, msg: str, status: int = 502) -> CodexZeroCanonPolicyError:
    return CodexZeroCanonPolicyError(code, msg, http_status=status)


@dataclass(frozen=True, slots=True)
class CodexZeroCanonRestrictions:
    model: str
    effort: str
    route_id: str = CODEX_V2_ROUTE_ID
    execution_kind: str = EXECUTION_KIND_EPHEMERAL
    ephemeral: bool = True
    tools: str = "off"
    sandbox: str = "read-only"
    approval_policy: str = "never"
    network_access: bool = False

    def thread_start_params(self, cwd: str) -> dict[str, object]:
        cleaned = cwd.strip()
        if not cleaned:
            raise _err("invalid_cwd", "Zero-Canon requires non-empty cwd", 400)
        return {"model": self.model, "cwd": cleaned, "ephemeral": self.ephemeral, "sandbox": self.sandbox, "approvalPolicy": self.approval_policy}

    def turn_start_params(self) -> dict[str, object]:
        return {"model": self.model, "effort": self.effort, "approvalPolicy": self.approval_policy, "sandboxPolicy": {"type": "readOnly", "networkAccess": self.network_access}}


@dataclass(frozen=True, slots=True)
class RequestedTurnSpec:
    model: str
    effort: str
    profile: str = ZERO_CANON_PROFILE
    backend: str = CODEX_BACKEND_ID
    route_id: str = CODEX_V2_ROUTE_ID


@dataclass(frozen=True, slots=True)
class ActualTurnObservation:
    model: str
    effort: str
    profile: str = ZERO_CANON_PROFILE
    backend: str = CODEX_BACKEND_ID
    route_id: str = CODEX_V2_ROUTE_ID
    thread_id: str = ""
    turn_id: str = ""
    terminal_status: str = ""
    tool_events_seen: int = 0


@dataclass(frozen=True, slots=True)
class ZeroCanonAttestationReceipt:
    requested: RequestedTurnSpec
    actual: ActualTurnObservation
    phase: str
    completeness: str

    @property
    def is_complete(self) -> bool:
        return self.phase == "completed" and self.completeness == "complete"

    def header_value(self) -> str:
        return format_attestation_header(self.actual.model, self.actual.effort, phase=self.phase, backend=self.actual.backend)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": ZERO_CANON_PROFILE, "backend": self.actual.backend, "route_id": self.actual.route_id,
            "tools": "off", "sandbox": "read-only", "approval": "never", "requested_model": self.requested.model,
            "actual_model": self.actual.model, "requested_effort": self.requested.effort, "actual_effort": self.actual.effort,
            "phase": self.phase, "completeness": self.completeness, "header": self.header_value(),
        }


@dataclass(frozen=True, slots=True)
class ErrorClassification:
    error_class: str
    http_status: int
    scope: str
    retryable: bool
    allow_same_model_failover: bool
    cancel_pgid: bool
    fail_closed: bool
    record_success: bool = False
    clear_penalty: bool = False


def validate_codex_model_effort(model: str, effort: str | None = None, *, default_if_missing: bool = True) -> tuple[str, str]:
    """Validate `(model, effort)` against CODEX_EFFORT_MATRIX without silent clamp."""
    norm_model = model.strip().lower()
    allowed = CODEX_EFFORT_MATRIX.get(norm_model)
    if allowed is None:
        raise _err("unsupported_model", f"Unsupported Codex model: {model!r}", 400)
    if effort is None:
        if default_if_missing:
            return norm_model, CODEX_DEFAULT_EFFORTS[norm_model]
        raise _err("unsupported_model_effort", f"Effort required for {norm_model}", 400)
    norm_effort = effort.strip().lower()
    if norm_effort not in allowed:
        raise _err("unsupported_model_effort", f"Unsupported effort {effort!r} for {norm_model}", 400)
    return norm_model, norm_effort


def build_zero_canon_restrictions(model: str, effort: str | None = None, *, route_id: str = CODEX_V2_ROUTE_ID) -> CodexZeroCanonRestrictions:
    """Build immutable Zero-Canon restrictions after strict model/effort validation."""
    valid_model, valid_effort = validate_codex_model_effort(model, effort)
    return CodexZeroCanonRestrictions(valid_model, valid_effort, route_id)


def sanitize_strict_request(payload: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of a strict Zero-Canon request with all tool fields stripped."""
    return {k: v for k, v in payload.items() if k not in STRICT_STRIPPED_REQUEST_KEYS}


def _has_tool_fields(mapping: Mapping[str, object]) -> bool:
    return mapping.get("is_tool_stop") is True or bool(mapping.get("tool_calls") or mapping.get("toolCalls"))


def is_upstream_tool_event(event: Mapping[str, object]) -> bool:
    """Detect upstream tool calls, command/file execution, or approval events."""
    method = event.get("method")
    if isinstance(method, str) and method in FORBIDDEN_TOOL_METHODS:
        return True
    if _has_tool_fields(event) or event.get("type") in FORBIDDEN_TOOL_ITEM_TYPES:
        return True
    raw_params = event.get("params")
    if not isinstance(raw_params, Mapping):
        return False
    params = cast(Mapping[str, object], raw_params)
    raw_item = params.get("item")
    item_t = cast(Mapping[str, object], raw_item).get("type") if isinstance(raw_item, Mapping) else None
    return _has_tool_fields(params) or item_t in FORBIDDEN_TOOL_ITEM_TYPES


def enforce_no_upstream_tool_event(event: Mapping[str, object], *, strict: bool = True) -> None:
    """Fail closed with zero_canon_tool_event_forbidden if strict mode sees a tool event."""
    if strict and is_upstream_tool_event(event):
        raise _err(ERR_TOOL_EVENT_FORBIDDEN, "Tool event forbidden in strict Zero-Canon")


def verify_turn_identity(requested: RequestedTurnSpec, actual: ActualTurnObservation) -> None:
    """Verify actual observed identity matches requested spec without drift."""
    if requested.profile == ZERO_CANON_PROFILE and actual.tool_events_seen > 0:
        raise _err(ERR_TOOL_EVENT_FORBIDDEN, f"{actual.tool_events_seen} tool event(s)")
    checks = (
        ("model", requested.model, actual.model), ("effort", requested.effort, actual.effort),
        ("profile", requested.profile, actual.profile), ("backend", requested.backend, actual.backend),
    )
    if drift := [name for name, exp, got in checks if exp != got]:
        raise _err("zero_canon_attestation_failed", f"Identity mismatch: {', '.join(drift)}")


def build_attestation_receipt(requested: RequestedTurnSpec, actual: ActualTurnObservation, *, phase: str) -> ZeroCanonAttestationReceipt:
    """Validate Zero-Canon proof invariants and produce an attestation receipt."""
    if phase not in ATTESTATION_PHASES or requested.profile != ZERO_CANON_PROFILE:
        raise _err("zero_canon_attestation_failed", f"Invalid phase={phase!r} or profile")
    verify_turn_identity(requested, actual)
    _ = validate_codex_model_effort(actual.model, actual.effort, default_if_missing=False)
    if phase == "completed" and actual.terminal_status != "completed":
        raise _err("upstream_incomplete_stream", f"terminal_status={actual.terminal_status!r}")
    return ZeroCanonAttestationReceipt(requested, actual, phase, "complete" if phase == "completed" else "admitted")


def format_attestation_header(model: str, effort: str, *, phase: str = "completed", backend: str = CODEX_BACKEND_ID) -> str:
    """Format canonical X-Zero-Canon-Attestation header after validating inputs."""
    m, e = validate_codex_model_effort(model, effort, default_if_missing=False)
    if phase not in ATTESTATION_PHASES:
        raise _err("zero_canon_attestation_failed", f"Invalid phase: {phase!r}")
    return f"profile={ZERO_CANON_PROFILE};backend={backend};tools=off;sandbox=read-only;approval=never;model={m};effort={e};phase={phase}"


def parse_attestation_header(header_value: str) -> dict[str, str]:
    """Parse canonical semicolon-delimited X-Zero-Canon-Attestation header."""
    if not header_value.strip():
        raise _err("zero_canon_attestation_failed", "Empty attestation header")
    parsed: dict[str, str] = {}
    for part in header_value.split(";"):
        if "=" not in part:
            raise _err("zero_canon_attestation_failed", f"Malformed token: {part!r}")
        key, val = (seg.strip() for seg in part.split("=", 1))
        if not key or not val or key in parsed:
            raise _err("zero_canon_attestation_failed", f"Invalid field: {part!r}")
        parsed[key] = val
    return parsed


def _is_rate_limit(lower_msg: str, status_code: int | None) -> bool:
    return status_code == 429 or any(k in lower_msg for k in ("429", "rate limit", "quota"))


def _classify_rate_limit(lower_msg: str) -> str:
    if any(m in lower_msg for m in _QUOTA_KEYS):
        return "quota_exhausted"
    if any(m in lower_msg for m in _TRANSIENT_KEYS):
        return "rate_limit_transient"
    return "rate_limit_unknown"


def _resolve_error_class(lower_msg: str, status_code: int | None, timeout_kind: str | None) -> str:
    if timeout_kind is not None and timeout_kind in _TIMEOUT_MAP:
        return _TIMEOUT_MAP[timeout_kind]
    if ERR_TOOL_EVENT_FORBIDDEN in lower_msg:
        return ERR_TOOL_EVENT_FORBIDDEN
    if status_code == 503 and "no available accounts" in lower_msg:
        return "credential_unavailable"
    if _is_rate_limit(lower_msg, status_code):
        return _classify_rate_limit(lower_msg)
    if any(m in lower_msg for m in _INCOMPLETE_KEYS):
        return "upstream_incomplete_stream"
    return "resident_protocol_failed"


def classify_error(
    message: str = "", *, status_code: int | None = None, timeout_kind: str | None = None, bytes_sent: int = 0
) -> ErrorClassification:
    """Classify failure by protocol/HTTP semantics only; never replay after bytes_sent > 0."""
    err_class = _resolve_error_class(message.lower(), status_code, timeout_kind)
    status, scope, retryable, failover, cancel_pgid, fail_closed = ERROR_TAXONOMY[err_class]
    pre_byte = bytes_sent <= 0
    return ErrorClassification(err_class, status, scope, retryable and pre_byte, failover and pre_byte, cancel_pgid, fail_closed)

"""Vendor-agnostic capabilities of session drivers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

TransportClass = Literal["stdio_resident", "local_sub_bridge", "http_passthrough"]


@dataclass(frozen=True, slots=True)
class DriverCapabilities:
    vendor_id: str
    protocol: str
    transport_class: TransportClass
    supports_warm_zero_canon: bool = False
    supports_logical_context_reset: bool = False
    supports_keyed_single_turn: bool = False
    supports_clean_home_attest: bool = False
    supports_affinity_routing: bool = False
    max_slots: int = 0
    max_wait_queue: int = 0
    max_rss_mb: int = 512
    certified_binary_hash: str = ""

    def __post_init__(self) -> None:
        if self.max_wait_queue <= 0 and self.max_slots > 0:
            object.__setattr__(self, "max_wait_queue", 2 * self.max_slots)


def _caps(vendor: str, protocol: str, transport: TransportClass, *, warm: bool, reset: bool, slots: int, affinity: bool = False, certified: str = "") -> DriverCapabilities:
    return DriverCapabilities(vendor, protocol, transport, warm, reset, True, warm, affinity, slots, 2 * slots, certified_binary_hash=certified)


DEFAULT_CAPABILITIES: Mapping[str, DriverCapabilities] = {
    "codex-app-server-v2": _caps("codex", "codex-app-server-v2", "stdio_resident", warm=True, reset=True, slots=10),
    "claude-stream-json": _caps("claude", "claude-stream-json", "stdio_resident", warm=True, reset=False, slots=10),
    "msp-v1": _caps("muse", "msp-v1", "stdio_resident", warm=True, reset=True, slots=10),
    "opencode-acp": _caps("opencode", "opencode-acp", "stdio_resident", warm=True, reset=True, slots=10),
    "agy-stream-json": _caps("agy", "agy-stream-json", "stdio_resident", warm=True, reset=True, slots=16),
    "agy-bridge": _caps("agy", "agy-bridge", "local_sub_bridge", warm=True, reset=True, slots=16),
    "opencode-zen": _caps("opencode", "opencode-zen", "local_sub_bridge", warm=False, reset=True, slots=16, affinity=True),
    "http-passthrough": _caps("http", "http-passthrough", "http_passthrough", warm=False, reset=True, slots=64, affinity=True),
}


def effective_capabilities(
    protocol_or_vendor: str,
    *,
    runtime_binary_hash: str = "",
    registry: Mapping[str, DriverCapabilities] | None = None,
) -> DriverCapabilities:
    """Возвращает capabilities и отключает logical reset при дрейфе бинаря."""
    table = DEFAULT_CAPABILITIES if registry is None else registry
    key = str(protocol_or_vendor or "")
    found = table.get(key)
    if found is None:
        found = next((item for item in table.values() if item.vendor_id == key or item.protocol == key), None)
    if found is None:
        return DriverCapabilities(key, key, "http_passthrough")
    if found.certified_binary_hash and runtime_binary_hash and runtime_binary_hash != found.certified_binary_hash:
        return DriverCapabilities(
            found.vendor_id, found.protocol, found.transport_class, found.supports_warm_zero_canon,
            False, found.supports_keyed_single_turn, found.supports_clean_home_attest,
            found.supports_affinity_routing, found.max_slots, found.max_wait_queue,
            found.max_rss_mb, found.certified_binary_hash,
        )
    return found

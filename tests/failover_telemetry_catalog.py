"""Каталог маршрутов для интеграционных тестов телеметрии отказов (W2-B3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from tests.test_resident_precommit_failover import MODEL_ID
from tests.transport_wire_support import WireSettings


def _route_entries(specs: Sequence[tuple[str, str | None]]) -> list[dict[str, Any]]:
    return [
        {
            "route_id": name,
            "backend": name,
            "weight": 100 if idx == 0 else 0,
            "priority": 10 * (idx + 1),
        }
        for idx, (name, _) in enumerate(specs)
    ]


def _model_entry(first: str, routes: list[dict[str, Any]]) -> dict[str, Any]:
    active = json.dumps(
        [{"backend": first, "route_id": first, "weight": 100}],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "id": MODEL_ID,
        "backend": first,
        "efforts": ["low", "medium", "high", "max"],
        "default_effort": "high",
        "context_window": 200000,
        "max_tokens": 64000,
        "input": ["text"],
        "images": {"status": "unsupported", "method": None},
        "routing": {
            "enabled": True,
            "algorithm": "weighted-sha256-v1",
            "catalog_hash": hashlib.sha256(active).hexdigest(),
            "legacy_backend": first,
            "disabled_backend": first,
            "routes": routes,
        },
    }


def _backend_entry(name: str, url: str | None) -> dict[str, Any]:
    if url is None:
        return {
            "kind": "stdio_resident",
            "enabled": True,
            "owned_by": f"{name}-bridge",
        }
    return {
        "kind": "passthrough",
        "base_url": url,
        "enabled": True,
        "max_concurrent": 1,
        "owned_by": f"{name}-bridge",
    }


def build_catalog(specs: Sequence[tuple[str, str | None]]) -> dict[str, Any]:
    """Каталог: spec = (backend_id, base_url | None); None — CLI (stdio_resident), иначе passthrough."""
    model = _model_entry(specs[0][0], _route_entries(specs))
    return {
        "schema": 3,
        "models": {MODEL_ID: model},
        "order": [MODEL_ID],
        "backends": {name: _backend_entry(name, url) for name, url in specs},
        "backend_order": [name for name, _ in specs],
        "image_limits": {"max_body_bytes": WireSettings().max_body_bytes},
    }

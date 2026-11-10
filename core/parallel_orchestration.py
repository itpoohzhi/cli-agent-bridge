from __future__ import annotations

import os
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .model_resolver import resolve_model
from .resident_pool import ResidentSlot, SlotKey

IDLE_TTL_S = float(os.getenv("BRIDGE_IDLE_TTL_S", "300"))
STARTUP_TIMEOUT_S = float(os.getenv("BRIDGE_STARTUP_TIMEOUT_S", "180"))
TURN_TIMEOUT_S = float(os.getenv("BRIDGE_TURN_TIMEOUT_S", "60"))
HEALTH_PROBE_TIMEOUT_S = float(
    os.getenv("BRIDGE_HEALTH_PROBE_TIMEOUT_S", "10")
)
RESET_TIMEOUT_S = float(os.getenv("BRIDGE_RESET_TIMEOUT_S", "20"))


class PoolConfig:
    def __init__(
        self,
        idle_ttl_s: float = IDLE_TTL_S,
        startup_timeout_s: float = STARTUP_TIMEOUT_S,
        turn_timeout_s: float = TURN_TIMEOUT_S,
        concurrency: int = 4,
        health_probe_timeout_s: float = HEALTH_PROBE_TIMEOUT_S,
        reset_timeout_s: float = RESET_TIMEOUT_S,
        **kwargs: Any,
    ) -> None:
        self.idle_ttl_s = float(kwargs.get("idle_ttl", idle_ttl_s))
        self.startup_timeout_s = float(
            kwargs.get("startup_timeout", startup_timeout_s)
        )
        self.turn_timeout_s = float(kwargs.get("turn_timeout", turn_timeout_s))
        self.concurrency = concurrency
        self.health_probe_timeout_s = health_probe_timeout_s
        self.reset_timeout_s = reset_timeout_s

    @property
    def idle_ttl(self) -> float:
        return self.idle_ttl_s

    @property
    def startup_timeout(self) -> float:
        return self.startup_timeout_s

    @property
    def turn_timeout(self) -> float:
        return self.turn_timeout_s


class ResidentSpec:
    def __init__(self, model_id: str, slots: int = 1) -> None:
        self.model_id = model_id
        self.model = model_id
        self.id = model_id
        self.slots = slots
        self.count = slots

    def __str__(self) -> str:
        return self.model_id


def _field(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None

    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def parse_resident_models(value: Any = None) -> list[Any]:
    if value is None:
        value = os.getenv("BRIDGE_RESIDENT_MODELS", "")

    if isinstance(value, str):
        entries: Iterable[Any] = value.split(",")
    elif isinstance(value, Mapping):
        entries = value.items()
    else:
        entries = value or ()

    result: list[Any] = []
    model_id: Any
    slots: Any
    for entry in entries:
        if isinstance(entry, ResidentSpec):
            result.append(entry)
            continue

        if isinstance(entry, tuple) and len(entry) == 2:
            model_id, slots = entry
        elif isinstance(entry, Mapping):
            model_id = _field(entry, "model_id", "model", "id")
            slots = _field(entry, "slots", "count")
            if slots is None:
                slots = 1
        else:
            text = str(entry).strip()
            if not text:
                continue
            if ":" in text:
                model_id, slots_text = text.rsplit(":", 1)
                model_id = model_id.strip()
                slots = int(slots_text.strip())
            else:
                model_id = text
                slots = 1

        model_id = str(model_id).strip()
        if not model_id:
            continue

        slots = int(slots)
        if slots < 1:
            raise ValueError(
                f"resident model '{model_id}' must have at least one slot"
            )
        result.append(ResidentSpec(model_id, slots))

    return result


@dataclass
class CatalogValidationResult:
    errors: list[str]


def validate_catalog(
    catalog: Any,
    resident_models: list[str] | None = None,
) -> Any:
    del resident_models

    models: Any = getattr(catalog, "models", None)
    if models is None:
        if isinstance(catalog, Mapping):
            models = catalog.get("models", catalog)
        else:
            models = catalog

    backends: Any = getattr(catalog, "backends", None)
    if not backends and isinstance(catalog, Mapping):
        backends = catalog.get("backends", {})
    backends = backends or {}

    if isinstance(models, Mapping):
        model_items = models.items()
    else:
        model_items = ()

    errors: list[str] = []
    for mid, cfg in model_items:
        backend = cfg.get("backend") if isinstance(cfg, Mapping) else None
        if backend is None or (backends and backend not in backends):
            errors.append(f"model '{mid}' missing backend or route")

    return CatalogValidationResult(errors=errors)


class ReadinessReport:
    def __init__(self, ready: bool, not_ready: list[str], state: str) -> None:
        self.ready = ready
        self.not_ready = not_ready
        self.state = state
        self.degraded = not ready


class ResidentPool:
    async def evict_idle(self) -> None:
        now = self.clock.value if self.clock else time.monotonic()
        for slot_k, slot in list(self.slots.items()):
            if not slot.pinned and now - slot.last_used_at > self.config.idle_ttl:
                slot.state = "EVICTED"
                if slot.handle is not None and hasattr(slot.handle, "stop"):
                    await slot.handle.stop()
                del self.slots[slot_k]

    def __init__(
        self,
        catalog: Any,
        adapter_factory: Any = None,
        resident: Any = None,
        config: Any = None,
        clock: Any = None,
    ) -> None:
        self.catalog = catalog
        self.adapter_factory = adapter_factory
        self.resident = (
            parse_resident_models(resident)
            if not isinstance(resident, list)
            else resident
        )
        self.config = config or PoolConfig()
        self.clock = clock
        self.slots: dict[str, ResidentSlot] = {}

    def key_for(self, model_id: str) -> SlotKey:
        models: Any = getattr(self.catalog, "models", None)
        if models is None and isinstance(self.catalog, Mapping):
            models = self.catalog.get("models", self.catalog)
        elif models is None:
            models = self.catalog

        aliases: Any = getattr(self.catalog, "aliases", None)
        if aliases is None and isinstance(self.catalog, Mapping):
            aliases = self.catalog.get("aliases", {})
        elif aliases is None:
            aliases = {}

        resolved = resolve_model(model_id, models, aliases)
        models_dict = models
        cfg = models_dict.get(resolved.base_id, {}) if isinstance(models_dict, Mapping) else {}
        adapter = (
            resolved.adapter
            or _field(cfg, "backend", "adapter")
            or getattr(self.config, "default_adapter", "fake")
        )
        return SlotKey(
            adapter=adapter,
            backend_id=resolved.backend_id,
            effort=resolved.effort,
        )

    def slot_for(self, model_id: str, effort: str | None = None) -> ResidentSlot | None:
        key = self.key_for(model_id)
        eff = effort if effort is not None else key.effort
        slot_k = f"{key.backend_id}:{eff}"
        slot = self.slots.get(slot_k)
        if slot is not None:
            if not slot.pinned and self.clock is not None:
                if self.clock.value - slot.last_used_at > self.config.idle_ttl:
                    slot.state = "EVICTED"
            if slot.state == "EVICTED":
                return None
            return slot
        return None

    async def prewarm(self) -> None:
        for spec in self.resident:
            mid = getattr(spec, "model_id", str(spec))
            key = self.key_for(mid)
            slot_k = f"{key.backend_id}:{key.effort}"
            try:
                adapter = self.adapter_factory(key)
                await adapter.start()
                now = self.clock.value if self.clock else time.monotonic()
                self.slots[slot_k] = ResidentSlot(
                    key=key,
                    state="READY",
                    handle=adapter,
                    pinned=True,
                    last_used_at=now,
                )
            except Exception as e:
                self.slots[slot_k] = ResidentSlot(
                    key=key,
                    state="FAILED",
                    handle=None,
                    last_error=str(e),
                    pinned=True,
                )

    async def execute_turn(self, model_id: str, request: Any) -> Any:
        key = self.key_for(model_id)
        slot_k = f"{key.backend_id}:{key.effort}"
        slot = self.slots.get(slot_k)
        now = self.clock.value if self.clock else time.monotonic()
        if slot is None:
            adapter = self.adapter_factory(key)
            await adapter.start()
            slot = ResidentSlot(
                key=key,
                state="READY",
                handle=adapter,
                pinned=False,
                last_used_at=now,
            )
            self.slots[slot_k] = slot
        slot.last_used_at = now
        try:
            await slot.handle.reset_context()
        except Exception:
            slot.state = "RECYCLING"
            raise
        return await slot.handle.execute_turn(request)

    def readiness(self) -> ReadinessReport:
        not_ready = []
        for spec in self.resident:
            mid = getattr(spec, "model_id", str(spec))
            key = self.key_for(mid)
            slot_k = f"{key.backend_id}:{key.effort}"
            slot = self.slots.get(slot_k)
            if slot is None or slot.state != "READY":
                not_ready.append(mid)
        return ReadinessReport(
            ready=len(not_ready) == 0,
            not_ready=not_ready,
            state="ready" if len(not_ready) == 0 else "degraded",
        )


class PoolSupervisor:
    async def watchdog_once(self) -> None:
        await self.check_once()

    def __init__(
        self,
        pool: ResidentPool,
        interval_s: float | None = None,
    ) -> None:
        self.pool = pool
        self.interval_s = (
            interval_s
            if interval_s is not None
            else getattr(pool.config, "supervisor_interval_s", None)
        )

    async def check_once(self) -> None:
        for slot_k, slot in list(self.pool.slots.items()):
            if slot.handle is not None and not slot.handle.is_alive():
                new_adapter = self.pool.adapter_factory(slot.key)
                await new_adapter.start()
                slot.handle = new_adapter
                slot.state = "READY"

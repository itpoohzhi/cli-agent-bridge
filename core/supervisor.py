from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any

from .resident_pool import ResidentPoolManager, ResidentSlot, SlotState


def _backoff_base() -> float:
    raw = os.getenv("BRIDGE_RESTART_BACKOFF_S")
    if raw is None or not raw.strip():
        return 1.0
    value = float(raw)
    if value < 0:
        raise ValueError("BRIDGE_RESTART_BACKOFF_S must be non-negative")
    return value


async def _await_result(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class LifecycleSupervisor:
    def __init__(
        self,
        pool: ResidentPoolManager,
        interval_s: float = 15.0,
    ) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self.pool = pool
        self.interval_s = interval_s
        self._restart_backoff_s = _backoff_base()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._failures: dict[int, int] = {}
        self._recycling: set[int] = set()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> asyncio.Task[None]:
        if self.running:
            assert self._task is not None
            return self._task
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self.run(),
            name="resident-pool-supervisor",
        )
        return self._task

    async def run(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self.check_once()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_s,
                    )
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise

    async def check_once(self) -> None:
        checks = [
            asyncio.create_task(self._check_slot(slot))
            for slot in self.pool.iter_slots()
            if slot.state == SlotState.READY.value
        ]
        if checks:
            await asyncio.gather(*checks, return_exceptions=True)
        await self.pool.evict_idle_unpinned()

    async def _check_slot(self, slot: ResidentSlot) -> None:
        slot_id = id(slot)
        if slot_id in self._recycling or slot.state != SlotState.READY.value:
            return

        adapter = self.pool.adapter_for(slot.key)
        health_check = getattr(adapter, "health_check", None)
        if health_check is None or not callable(health_check):
            slot.last_error = "adapter does not implement health_check"
            await self._schedule_recycle(slot, slot.last_error)
            return

        try:
            result = await _await_result(health_check(slot.handle))
            healthy = True if result is None else bool(result)
        except BaseException as exc:
            healthy = False
            reason = f"{type(exc).__name__}: {exc}"
        else:
            reason = "health check reported an unhealthy slot"

        if healthy:
            self._failures.pop(slot_id, None)
            return
        slot.last_error = reason
        await self._schedule_recycle(slot, reason)

    async def _schedule_recycle(self, slot: ResidentSlot, reason: str) -> None:
        slot_id = id(slot)
        if slot_id in self._recycling:
            return
        self._recycling.add(slot_id)
        failures = self._failures.get(slot_id, 0)
        delay = self._restart_backoff_s * (2**failures)
        self._failures[slot_id] = failures + 1
        try:
            if delay > 0:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                    return
                except asyncio.TimeoutError:
                    pass
            if not self._stop_event.is_set():
                await self.pool.recycle_slot(slot, reason)
                self._failures.pop(slot_id, None)
        finally:
            self._recycling.discard(slot_id)

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        self._task = None
        if task is None:
            return
        if task is asyncio.current_task():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def shutdown(self, shutdown_pool: bool = False) -> None:
        await self.stop()
        if shutdown_pool:
            await self.pool.shutdown()

    async def __aenter__(self) -> "LifecycleSupervisor":
        self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.stop()

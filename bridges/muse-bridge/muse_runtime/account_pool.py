from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Condition, Lock
from typing import Sequence

_LOG = logging.getLogger(__name__)


@dataclass
class AccountSlot:
    """Слот аккаунта с независимыми временами привязки и активности."""

    slot_id: str
    account_id: str
    bound_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)
    is_healthy: bool = True
    in_use: bool = False
    failure_count: int = 0
    success_count: int = 0

    def touch(self) -> None:
        """Обновить только время последней активности."""
        self.last_seen_at = time.time()


@dataclass(frozen=True)
class AccountPoolConfig:
    """Ограничения параллелизма, доступности и ожидания."""

    max_concurrent: int = 4
    n_floor: int = 1
    acquire_timeout_s: float = 30.0
    idle_timeout_s: float = 300.0

    def __post_init__(self) -> None:
        if self.max_concurrent < 1 or self.n_floor < 1:
            raise ValueError("Параллелизм и минимальный запас должны быть положительными")
        for value in (self.acquire_timeout_s, self.idle_timeout_s):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Таймаут должен быть конечным и неотрицательным")


class AccountPool:
    """Потокобезопасный пул с карантином и защитой Panic-Open."""

    def __init__(
        self,
        config: AccountPoolConfig | None = None,
        accounts: Sequence[str] | None = None,
    ) -> None:
        self._config: AccountPoolConfig = config or AccountPoolConfig()
        self._lock: Lock = Lock()
        self._condition: Condition = Condition(self._lock)
        self._semaphore: BoundedSemaphore = BoundedSemaphore(
            self._config.max_concurrent
        )
        identifiers = (
            tuple(accounts)
            if accounts is not None
            else tuple(f"account-{i}" for i in range(self._config.max_concurrent))
        )
        with self._condition:
            self._slots: dict[str, AccountSlot] = {}
            self._quarantined_slots: dict[str, AccountSlot] = {}
            for index, account_id in enumerate(identifiers):
                now = time.time()
                slot = AccountSlot(f"slot-{index}", account_id, now, now)
                self._slots[slot.slot_id] = slot

    @property
    def quarantined_slots(self) -> dict[str, AccountSlot]:
        """Вернуть снимок карантина по идентификаторам слотов."""
        with self._condition:
            return dict(self._quarantined_slots)

    def acquire(self, timeout: float | None = None) -> AccountSlot | None:
        """Получить слот, ограничивая суммарное ожидание заданным таймаутом."""
        duration = self._config.acquire_timeout_s if timeout is None else timeout
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Таймаут должен быть конечным и неотрицательным")
        deadline = time.monotonic() + duration
        if not self._semaphore.acquire(timeout=duration):
            return None
        claimed = False
        try:
            with self._condition:
                while self._slots:
                    for slot in self._slots.values():
                        if slot.is_healthy and not slot.in_use:
                            slot.touch()
                            slot.in_use = True
                            claimed = True
                            return slot
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    _ = self._condition.wait(remaining)
                return None
        finally:
            if not claimed:
                self._semaphore.release()

    def release(self, slot: AccountSlot, success: bool = True) -> None:
        """Вернуть выданный слот; повторный или чужой возврат игнорируется."""
        with self._condition:
            if self._slots.get(slot.slot_id) is not slot or not slot.in_use:
                return
            if success:
                slot.success_count += 1
            else:
                slot.failure_count += 1
                _ = self._mark_unhealthy_locked(slot)
            slot.in_use = False
            self._semaphore.release()
            self._condition.notify_all()

    def _mark_unhealthy_locked(self, slot: AccountSlot) -> bool:
        """Поместить слот в карантин под блокировкой с проверкой запаса."""
        if self._slots.get(slot.slot_id) is not slot:
            return False
        if not slot.is_healthy:
            return True
        healthy = sum(item.is_healthy for item in self._slots.values())
        if healthy - 1 < self._config.n_floor:
            _LOG.warning(
                "Panic-Open: слот %s сохранён, здоровых=%d, минимум=%d",
                slot.slot_id, healthy, self._config.n_floor,
            )
            return False
        slot.is_healthy = False
        self._quarantined_slots[slot.slot_id] = slot
        return True

    def mark_unhealthy(self, slot: AccountSlot) -> bool:
        """Поместить слот в карантин, если разрешает предикат Panic-Open."""
        with self._condition:
            result = self._mark_unhealthy_locked(slot)
            self._condition.notify_all()
            return result

    def mark_healthy(self, slot: AccountSlot) -> bool:
        """Снять карантин, сохранив привязку, счётчики и текущую занятость."""
        with self._condition:
            if self._slots.get(slot.slot_id) is not slot:
                return False
            slot.is_healthy = True
            _ = self._quarantined_slots.pop(slot.slot_id, None)
            self._condition.notify_all()
            return True

    def heartbeat(self, slot: AccountSlot) -> bool:
        """Обновить активность известного слота, не изменяя привязку."""
        with self._condition:
            if self._slots.get(slot.slot_id) is not slot:
                return False
            slot.touch()
            return True

    def get_active_count(self) -> int:
        """Вернуть число выданных и ещё не возвращённых слотов."""
        with self._condition:
            return sum(slot.in_use for slot in self._slots.values())

    def get_healthy_count(self) -> int:
        """Вернуть число здоровых слотов, включая занятые."""
        with self._condition:
            return sum(slot.is_healthy for slot in self._slots.values())

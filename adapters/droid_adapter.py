"""Адаптер Factory Droid (`droid exec --input-format stream-jsonrpc`) — тонкая оболочка.

Фаза 1 по ADR 0002: инварианты ADR 0001 (L -> P -> T, receipt-допуск образа с schema 2,
`settings_profile`/`tools_policy`, резидентные процессы на чат, idle-revive, изоляция ходов,
байтовые бюджеты) остаются в `server.py` без единого изменения, потому что на них завязаны
~20 тестовых модулей. Адаптер даёт им единый контракт `BackendAdapter` и делегирует работу
хосту (`host` — модуль `server`; адаптер его НЕ импортирует, чтобы не было цикла).
Поведение для моделей droid байт-в-байт прежнее.
"""

from __future__ import annotations

from typing import Any

from core.backend_adapter import (
    SESSIONS_RESIDENT,
    STREAMING_EMULATED,
    BackendAdapter,
    BackendNotSupported,
)


class DroidAdapter(BackendAdapter):
    kind = "droid"
    capabilities = {
        "sessions": SESSIONS_RESIDENT,
        "streaming": STREAMING_EMULATED,  # вывод удерживается до checkpoint и отдаётся срезами
        "autonomy": True,
        "usage": "exact",
    }

    @property
    def max_concurrent(self) -> int:
        """Ёмкость P (cap процессов droid) — `MAX_CONCURRENT` хоста, как до хаба."""
        return int(self.host.MAX_CONCURRENT)

    def get_models(self) -> list:
        return self._catalog_models()

    def qualify(self) -> tuple:
        """Допуск образа по receipt (schema 2): ok | not_required | invalid."""
        state = self.host._receipt_state()
        return (state != "invalid", f"receipt_{state}")

    def is_healthy(self) -> bool:
        return bool(self.host._receipt_state() != "invalid")

    def preflight(self) -> tuple:
        """Канонический лончер на месте (проверка до SSE и до любого запуска)."""
        try:
            self.host._launcher()
        except self.host.LauncherUnavailable:
            return (False, "launcher_unavailable")
        return (True, "")

    def active_count(self) -> int:
        with self.host._active_lock:
            return len(self.host._active)

    def spawn_session(self, ctx: dict) -> Any:
        """Сессия droid открывается лениво планом хода (`_make_plan`: hot|restore|rebase|cold).

        Отдельного «пустого» spawn контракт ADR 0001 не допускает: PENDING записывается
        до первого `add_user_message`, поэтому вызов вне хода отклоняется.
        """
        raise BackendNotSupported("session_opened_by_turn_plan")

    def execute_turn(self, ctx: dict, sse_writer: Any) -> dict:
        """Ход через прежний путь `Handler._run_once` (ресурсы L -> P -> T, ретраи, checkpoint)."""
        handler = ctx["handler"]
        return handler._run_once(ctx, ctx.get("keepalive"))

    def close_session(self, sid: str) -> None:
        """Закрыть процесс droid с данным SID (term); неизвестный SID — тихо."""
        with self.host._active_lock:
            procs = list(self.host._rpc_procs.values())
        for proc in procs:
            if getattr(proc, "sid", "") == sid:
                self.host._close_async(proc, "term")

    def shutdown(self) -> None:
        self.host.shutdown_all()

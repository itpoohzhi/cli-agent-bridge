"""Адаптер Factory Droid (`droid exec --input-format stream-jsonrpc`) — тонкая оболочка.

RPC-машина droid остаётся в `server.py`; фасад маршрутизирует ход через адаптер.
Инварианты ADR 0001 (L -> P -> T, receipt-допуск образа с schema 2, `settings_profile`/
`tools_policy`, резидентные процессы на чат, idle-revive, изоляция ходов, байтовые бюджеты)
адаптер даёт им единый контракт `BackendAdapter` и делегирует работу хосту (`host` — модуль
`server`; адаптер его НЕ импортирует, чтобы не было цикла). Поведение для моделей droid
байт-в-байт прежнее.
"""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, Optional, cast

from core.backend_adapter import (
    SESSIONS_RESIDENT,
    STREAMING_EMULATED,
    BackendAdapter,
    BackendNotSupported,
    BackendModel,
    Capabilities,
    Qualification,
    StreamSink,
    ToolCall,
    ToolFunction,
    TurnContext,
    TurnEvent,
    TurnResult,
    Usage,
)


class DroidAdapter(BackendAdapter):
    kind = "droid"
    capabilities = Capabilities(SESSIONS_RESIDENT, STREAMING_EMULATED, True, "exact")

    @property
    def max_concurrent(self) -> int:
        """Ёмкость P (cap процессов droid) — `MAX_CONCURRENT` хоста, как до хаба."""
        return int(self.host.MAX_CONCURRENT)

    def get_models(self) -> list[BackendModel]:
        return self._catalog_models()

    def qualify(self) -> Qualification:
        """Допуск образа по receipt (schema 2): ok | not_required | invalid."""
        state = self.host._receipt_state()
        return Qualification(state != "invalid", f"receipt_{state}")

    def is_healthy(self) -> bool:
        return bool(self.host._receipt_state() != "invalid")

    def preflight(self) -> Qualification:
        """Канонический лончер на месте (проверка до SSE и до любого запуска)."""
        try:
            self.host._launcher()
        except self.host.LauncherUnavailable:
            return Qualification(False, "launcher_unavailable")
        return Qualification(True, "")

    def active_count(self) -> int:
        with self.host._active_lock:
            return len(self.host._active)

    def spawn_session(self, ctx: TurnContext) -> object:
        """Сессия droid открывается лениво планом хода (`_make_plan`: hot|restore|rebase|cold).

        Отдельного «пустого» spawn контракт ADR 0001 не допускает: PENDING записывается
        до первого `add_user_message`, поэтому вызов вне хода отклоняется.
        """
        raise BackendNotSupported("session_opened_by_turn_plan")

    def execute_turn(
        self, ctx: TurnContext, sse_writer: Optional[StreamSink]
    ) -> TurnResult:
        """Единственное место преобразования DTO в legacy dict и обратно; RPC не меняется."""
        legacy = {f.name: getattr(ctx, f.name) for f in fields(ctx)}
        legacy["rpc"] = asdict(ctx.rpc)
        legacy["rpc"]["items"] = [asdict(item) for item in ctx.rpc.items]
        legacy["images"] = [asdict(image) for image in ctx.images]
        handler = cast(Any, ctx.handler)
        raw = handler._run_once(legacy, ctx.keepalive)
        usage = raw.get("usage") or {}

        def tool_call(call: dict) -> ToolCall:
            fn = call["function"]
            return ToolCall(
                call["index"],
                call["id"],
                ToolFunction(fn["name"], fn["arguments"]),
                call["type"],
            )

        events = (
            tuple(
                TurnEvent(kind, tool_call(value) if kind == "tool_call" else str(value))
                for kind, value in raw["events"]
            )
            if "events" in raw
            else None
        )
        return TurnResult(
            state=raw["state"],
            rc=raw["rc"],
            text=raw.get("text") or "",
            reasoning=raw.get("reasoning") or "",
            err=raw.get("err") or "",
            usage=Usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
            tool_calls=tuple(tool_call(call) for call in raw.get("tool_calls") or ()),
            events=events,
        )

    def close_session(self, sid: str) -> None:
        """Закрыть процесс droid с данным SID (term); неизвестный SID — тихо."""
        with self.host._active_lock:
            procs = list(self.host._rpc_procs.values())
        for proc in procs:
            if getattr(proc, "sid", "") == sid:
                self.host._close_async(proc, "term")

    def shutdown(self) -> None:
        self.host.shutdown_all()

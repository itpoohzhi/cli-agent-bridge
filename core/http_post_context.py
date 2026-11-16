"""Контекст одного POST и поздно связанные порты HTTP-фасада."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from http.client import HTTPMessage
from typing import Any, BinaryIO, Protocol


class BodyBudget(Protocol):
    """Существующий владелец допуска байт тела запроса."""

    def reserve(self, amount: int) -> bool: ...

    def release(self, amount: int) -> None: ...


class PostHandler(Protocol):
    """Поверхность существующего HTTP handler, без импорта server."""

    path: str
    headers: HTTPMessage
    rfile: BinaryIO
    client_address: tuple[str, int]
    close_connection: bool
    _headers_already_sent: bool
    _trace: object | None
    _response_status: int
    _active_managed_turn: object | None
    _context_pruned: object | None
    _parsed_req: dict[str, Any]
    _send: Callable[..., None]
    _reject: Callable[..., None]
    _reply_error: Callable[..., None]
    _telemetry_begin: Callable[[], None]
    _telemetry_meta_request: Callable[[dict[str, Any]], None]
    _is_subagent_request: Callable[[], bool]
    _handle_models_refresh: Callable[[], None]
    _handle_quarantine_post: Callable[[], None]


class ClientTokenAdapter(Protocol):
    """Только проверка токена существующего passthrough-адаптера."""

    def validate_client_token(self, token: str) -> bool: ...


class PostBackends(Protocol):
    """Живой реестр, не сохранённая копия списка адаптеров."""

    def adapters(self) -> Iterable[object]: ...


class PostFlag(Protocol):
    """Порт существующего динамического флага."""

    def enabled(self) -> bool: ...


class PostLifecycle(Protocol):
    """Поздние вызовы существующего drain-контроллера."""

    def is_draining(self) -> bool: ...

    def wait_for_drain_hold(self, *, is_subagent: bool) -> bool: ...

    def draining_response(
        self, *, is_subagent: bool,
    ) -> tuple[int, dict[str, str], dict[str, Any]]: ...


class PostTurns(Protocol):
    """Существующий менеджер отмены хода и проверки владельца."""

    def cancel_turn(self, turn_id: str, *, owner_token_hash: str) -> None: ...

    def get_turn_snapshot(
        self, turn_id: str, *, owner_token_hash: str,
    ) -> dict[str, Any]: ...


class ProviderChatPattern(Protocol):
    """Только необходимая операция регулярного выражения host."""

    def match(self, path: str) -> Any: ...


class PostHost(Protocol):
    """Порты читаются при вызове, чтобы сохранить host monkeypatch/reload.

    Передаётся сам host, а не снимок его globals или набор bound callbacks.
    Владельцы budget и turn manager остаются в существующем фасаде.
    """

    FLEET: dict[str, Any]
    BACKENDS: PostBackends
    LIFECYCLE: PostLifecycle
    TURN_MANAGER: PostTurns
    PASSTHROUGH_AUTH_FLAG_SOURCE: PostFlag
    PassthroughAdapter: type[ClientTokenAdapter]
    PROVIDER_SCOPES: Mapping[str, object]
    REQUEST_ATTRIBUTION_ENABLED: bool
    _LOOPBACK_PEERS: Iterable[str]
    _CHAT_PATHS: Iterable[str]
    _PROVIDER_CHAT_RE: ProviderChatPattern
    _shutting_down: bool
    _budget: BodyBudget | None
    _auth_ok: Callable[[PostHandler], bool]
    _extract_auth_token: Callable[[PostHandler], str]
    _owner_token_hash: Callable[[PostHandler], str]
    _is_detached_enabled: Callable[[], bool]
    _is_drain_enabled: Callable[[], bool]
    _enforce_forward_kill_switch: Callable[[], None]
    validate_turn_id: Callable[[str], bool]
    _resolve_trace: Callable[[dict[str, str], dict[str, Any]], object]
    _strip_passthrough_env: Callable[
        [bytes, dict[str, Any]], tuple[bytes, dict[str, Any]]
    ]


class PostRequestContext:
    """Владеет телом и резервом одного уже принятого HTTP-запроса.

    read_post_request удерживает резерв до dispatch; его владелец обязан
    вызвать release_body в finally. При отказе ingress освобождает его сам.
    Остальной cleanup managed turn/delivery по-прежнему принадлежит dispatch.
    """

    def __init__(self, handler: PostHandler, host: PostHost) -> None:
        self.handler = handler
        self.host = host
        self.path = handler.path.split("?", 1)[0]
        self.cancel_turn_id: str | None = None
        self.provider_id: str | None = None
        self.hub_auth_ok = False
        self.deferred_passthrough_auth = False
        self.content_length = 0
        self.raw = b""
        self._request: dict[str, Any] = {}
        self._transport_controls: dict[str, Any] = {}
        self._body_budget: BodyBudget | None = None
        self._body_reserved = 0

    @property
    def request(self) -> dict[str, Any]:
        """Возвращает отдельный верхний уровень, не отдавая свой словарь."""
        return dict(self._request)

    @property
    def transport_controls(self) -> dict[str, Any]:
        """Сохраняет исходный body seed для проверки и выбора до egress."""
        return dict(self._transport_controls)

    def prepare_route(self, raw: bytes, request: Mapping[str, Any]) -> None:
        """Принимает новое представление тела без изменения словаря caller."""
        self.raw = raw
        self._request = dict(request)

    def consume_controls(self) -> None:
        """Потребляет body seed даже при выключенном routing, без RNG."""
        if "transport_seed" not in self._request:
            return
        self._transport_controls["transport_seed"] = self._request["transport_seed"]
        request = dict(self._request)
        del request["transport_seed"]
        self.prepare_route(json.dumps(request, ensure_ascii=False).encode("utf-8"), request)

    def reserve_body(self, length: int) -> bool:
        """Закрепляет фактического владельца резерва до чтения тела."""
        if self._body_reserved:
            raise RuntimeError("post_body_already_reserved")
        budget = self.host._budget
        if budget is not None and length:
            if not budget.reserve(length):
                return False
            self._body_budget = budget
            self._body_reserved = length
        self.content_length = length
        return True

    def release_body(self) -> None:
        """Освобождает именно исходный budget, не новый после reload."""
        budget, reserved = self._body_budget, self._body_reserved
        self._body_budget = None
        self._body_reserved = 0
        if reserved and budget is not None:
            budget.release(reserved)

    def send_error(
        self, status: int, kind: str, message: str, *, close: bool = True,
    ) -> None:
        """Сохраняет прежний формат _send и явное закрытие соединения."""
        if close:
            self.handler.close_connection = True
        self.handler._send(
            status, {"error": {"message": message, "type": kind, "code": status}},
        )

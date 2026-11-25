"""Тонкий адаптер резидентных stdio-процессов."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import os
import shlex
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import closing
from typing import Any, cast, override

from adapters.stdio_resident_delta import (
    execute_stdio_turn,
    format_stream_delta as _format_delta,  # noqa: F401
    sample_usage_enabled,
    stream_assembled_deltas,
)
from adapters.stdio_resident_runtime import (
    ResidentTrustConfig,
    build_resident_envelope_from_chat,
    extract_adapter_options,
    parse_require_auth_env,
    request_mapping,
    resolve_raw_argv,
)
from core import backend_adapter as _ba
from core.backend_adapter import (
    BackendAdapter,
    BackendModel,
    Capabilities,
    KindConstraints,
    Qualification,
    StreamSink,
    TurnContext,
    TurnResult,
)
from core.resident_identity import ResidentIdentity
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.protocol_driver import StdioProtocolDriver
from core.stdio_resident.resident_runtime import ResidentBridgeRuntime, ResidentTurnOptions
from core.stdio_resident.session_manager import StdioSessionManager

ADAPTER_API = _ba.ADAPTER_API
KIND = "stdio_resident"
_PROTOCOLS = (
    "stream-json", "stream-jsonrpc", "acp", "msp-v1", "opencode-acp",
    "claude-stream-json", "codex-app-server", "codex-app-server-v2",
    "agy-stream-json",
)
def _empty_catalog() -> Mapping[str, Any]:
    return {}


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else None


def _resolve_str(
    data: Mapping[str, Any],
    fallback: Mapping[str, Any] | None,
    key: str,
    default: str,
) -> str:
    for src in (data, fallback):
        if src is not None:
            val = src.get(key)
            if isinstance(val, str) and val:
                return val
    return default


class StdioResidentAdapter(BackendAdapter):
    uses_resident_identity: bool = True
    """Связывает контракт адаптера с универсальным resident-ядром."""

    CONSTRAINTS: KindConstraints = KindConstraints(
        max_concurrent_max=None,
        pin_required=False,
        base_url_allowed=False,
        api_key_env_allowed=False,
        options_schema={"protocol": _PROTOCOLS, "step_dedup": ("arbiter", "off")},
    )
    kind: str = KIND
    adapter_api: int = ADAPTER_API
    capabilities: Capabilities = Capabilities(
        sessions=_ba.SESSIONS_RESIDENT, streaming=_ba.STREAMING_NATIVE
    )

    def __init__(
        self,
        backend_id: str | Mapping[str, Any] = KIND,
        provider_config: Mapping[str, Any] | None = None,
        catalog_source: Callable[[], Mapping[str, Any]] | None = None,
        host: object | None = None,
        *,
        cli_argv: list[str] | tuple[str, ...] | str | None = None,
    ) -> None:
        if isinstance(backend_id, Mapping):
            actual_config: dict[str, Any] = dict(backend_id)
            actual_id = (
                str(provider_config or KIND) if isinstance(provider_config, str) else KIND
            )
        else:
            actual_id, actual_config = str(backend_id), dict(provider_config or {})
        super().__init__(actual_id, actual_config, catalog_source or _empty_catalog, host)
        self._has_catalog_source: bool = catalog_source is not None
        self._options: dict[str, Any] = extract_adapter_options(actual_config)
        from adapters.stdio_drivers import infer_protocol, resolve_pool_and_driver

        self._protocol: str = infer_protocol(actual_id, actual_config, self._options)
        self._config: StdioPoolConfig
        self._driver: StdioProtocolDriver
        self._config, self._driver = resolve_pool_and_driver(
            self._protocol, driver_config=actual_config
        )
        self._require_auth = parse_require_auth_env()
        self._hmac_secret: bytes = os.urandom(32)
        self._pool: ResidentProcessPool = ResidentProcessPool(self._config)
        self._runtime = ResidentBridgeRuntime(self._pool, self._driver, self._config)
        self._session_manager: StdioSessionManager = StdioSessionManager(
            self._pool, self._driver
        )
        raw_argv = resolve_raw_argv(cli_argv, self._options, actual_config)
        self._cli_argv: list[str] = self._parse_argv(raw_argv)

    @staticmethod
    def _parse_argv(value: object) -> list[str]:
        if isinstance(value, str):
            return shlex.split(value)
        if isinstance(value, list | tuple):
            return [str(arg) for arg in cast(Sequence[object], value)]
        return []

    def _sync_protocol(self) -> str:
        from adapters.stdio_drivers import infer_protocol, resolve_pool_and_driver

        resolved = infer_protocol(self.id, self.config, self._options)
        if resolved != self._protocol:
            self._protocol = resolved
            _, self._driver = resolve_pool_and_driver(
                resolved, driver_config=self.config
            )
            self._runtime = ResidentBridgeRuntime(self._pool, self._driver, self._config)
            self._session_manager = StdioSessionManager(self._pool, self._driver)
        return self._protocol

    def preflight_check(self) -> bool:
        """Сообщает фасаду, разрешён ли resident-путь флагом."""
        if not self._config.enabled:
            return False
        from adapters import stdio_drivers as drivers

        protocol = self._sync_protocol()
        checks: dict[str, Callable[[], bool]] = {
            "opencode-acp": drivers.is_opencode_resident_enabled,
            "msp-v1": drivers.is_resident_enabled,
            "codex-app-server-v2": drivers.is_codex_app_server_v2_enabled,
            "agy-stream-json": lambda: drivers.is_agy_resident_enabled(os.environ),
        }
        check = checks.get(protocol)
        return check() if check is not None else True

    def _effective_require_auth(self) -> bool:
        return bool(self._require_auth)

    def resident_identity_config(self) -> tuple[bytes, str, bool]:
        return (self._hmac_secret, self._protocol, self._effective_require_auth())

    def execute_chat(
        self,
        request: dict[str, Any] | Any,
        *,
        trusted_owner_hash: Any = None,
        auth_owner_hash: Any = None,
        trusted_identity: ResidentIdentity | None = None,
        **_kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        """Выполняет ход и выдаёт OpenAI-совместимые потоковые дельты."""
        _ = self._sync_protocol()
        data = request_mapping(request)
        trusted = auth_owner_hash if trusted_owner_hash is None else trusted_owner_hash
        require_auth = self._effective_require_auth()
        envelope, _raw_prompt = build_resident_envelope_from_chat(
            self.id,
            data,
            self._hmac_secret,
            ResidentTrustConfig(
                trusted_owner_hash=trusted,
                trusted_identity=trusted_identity,
                require_auth=require_auth,
                protocol=self._protocol,
            ),
        )
        validate_timeout = getattr(self._driver, "validate_timeout", None)
        if callable(validate_timeout):
            _ = validate_timeout(self._options)
        raw_context = _as_mapping(data.get("turn_context"))
        raw_cap = self._config.max_turn_output_bytes
        cap = max(1024, int(raw_cap if raw_cap else 4194304))
        options = ResidentTurnOptions(
            argv_builder=self._build_argv,
            cancel_event=data.get("_cancel_event"),
            require_auth=require_auth,
            extra_turn_context=dict(raw_context) if raw_context else {},
            max_output_bytes=cap if envelope.emulate_tools else None,
            terminal_validator=data.get("_terminal_validator"),
            keepalive=data.get("_keepalive"),
        )
        raw_sink = data.get("_turn_usage_sink")
        usage_sink = raw_sink if isinstance(raw_sink, list) else None
        mock_stream = vars(self._session_manager).get("execute_turn_stream")
        raw_stream = mock_stream() if callable(mock_stream) else self._runtime.execute_turn(envelope, options)
        with closing(raw_stream) as stream:
            yield from stream_assembled_deltas(
                stream,
                usage_enabled=sample_usage_enabled(data),
                usage_sink=usage_sink,
            )

    def _build_argv(self) -> list[str]:
        if not self._cli_argv:
            raise ValueError("stdio resident cli argv is not configured")
        return self._driver.build_argv(self._cli_argv, self._options)

    @override
    def get_models(self) -> list[BackendModel]:
        return self._catalog_models() if self._has_catalog_source else []

    @override
    def qualify(self) -> Qualification:
        if not self.preflight_check():
            return Qualification(False, "disabled")
        ok, reason = self._driver.verify_environment()
        return Qualification(ok, reason)

    @override
    def is_healthy(self) -> bool:
        return self.preflight_check()

    @override
    def spawn_session(self, ctx: TurnContext) -> object:
        _ = self._sync_protocol()
        return self._session_manager

    @override
    def execute_turn(self, ctx: TurnContext, sse_writer: StreamSink | None) -> TurnResult:
        return execute_stdio_turn(self, self._sync_protocol(), ctx, sse_writer)

    @override
    def close_session(self, sid: str) -> None:
        return None

    @override
    def shutdown(self, timeout_s: float | None = None) -> None:
        """Останавливает все дочерние процессы resident-пула."""
        self._pool.shutdown(timeout_s)

"""Тонкий адаптер резидентных stdio-процессов."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import os
import shlex
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, cast, override

from adapters.stdio_resident_delta import (
    execute_stdio_turn,
    format_stream_delta as _format_delta,  # noqa: F401
    sample_usage_enabled,
    stream_assembled_deltas,
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
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.protocol_driver import StdioProtocolDriver
from core.stdio_resident.session_manager import StdioSessionManager
from core.stdio_resident.types import SlotAffinityKey
from core.subbridge_zero_canon import normalize_review_profile

ADAPTER_API = _ba.ADAPTER_API
KIND = "stdio_resident"
_PROTOCOLS = (
    "stream-json", "stream-jsonrpc", "acp", "msp-v1", "opencode-acp",
    "claude-stream-json", "codex-app-server", "codex-app-server-v2",
    "agy-stream-json",
)
_ADAPTER_OPTION_KEYS = frozenset({
    "protocol", "cli_argv", "argv", "cli_args", "sandbox_flags",
    "output_format", "output_format_flag", "output_format_args", "step_dedup",
})


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
        self._options: dict[str, Any] = self._extract_options(actual_config)
        from adapters.stdio_drivers import infer_protocol, resolve_pool_and_driver

        self._protocol: str = infer_protocol(actual_id, actual_config, self._options)
        self._config: StdioPoolConfig
        self._driver: StdioProtocolDriver
        self._config, self._driver = resolve_pool_and_driver(
            self._protocol, driver_config=actual_config
        )
        self._pool: ResidentProcessPool = ResidentProcessPool(self._config)
        self._session_manager: StdioSessionManager = StdioSessionManager(
            self._pool, self._driver
        )
        raw_argv = self._resolve_raw_argv(cli_argv, self._options, actual_config)
        self._cli_argv: list[str] = self._parse_argv(raw_argv)

    @staticmethod
    def _extract_options(config: Mapping[str, Any]) -> dict[str, Any]:
        transport = _as_mapping(config.get("transport"))
        tr_bridge = _as_mapping(transport.get("bridge")) if transport is not None else None
        bridge = _as_mapping(config.get("bridge"))
        for container in (tr_bridge, bridge, config):
            if container is not None:
                opts = _as_mapping(container.get("options"))
                if opts is not None:
                    return dict(opts)
        return {k: v for k, v in config.items() if k in _ADAPTER_OPTION_KEYS}

    @staticmethod
    def _resolve_raw_argv(
        cli_argv: list[str] | tuple[str, ...] | str | None,
        options: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> object:
        if cli_argv is not None:
            return cli_argv
        transport = _as_mapping(config.get("transport"))
        tr_bridge = _as_mapping(transport.get("bridge")) if transport is not None else None
        bridge = _as_mapping(config.get("bridge"))
        sources = (
            (options, ("cli_argv", "argv")),
            (config, ("cli_argv", "wrapper")),
            (tr_bridge, ("cli_argv", "wrapper")),
            (bridge, ("cli_argv", "wrapper")),
        )
        for src, keys in sources:
            if src is None:
                continue
            for key in keys:
                if (val := src.get(key)) is not None:
                    return val
        return None

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

    def execute_chat(
        self, request: dict[str, Any] | Any, **_kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Выполняет ход и выдаёт OpenAI-совместимые потоковые дельты."""
        _ = self._sync_protocol()
        data = self._request_mapping(request)
        cwd = _resolve_str(data, None, "cwd", os.getcwd())
        norm_cwd = os.path.realpath(os.path.abspath(os.path.expanduser(cwd)))
        raw_ctx = _as_mapping(data.get("turn_context"))
        model = _resolve_str(data, raw_ctx, "model", "default")
        effort = _resolve_str(data, raw_ctx, "effort", "medium")
        profile = normalize_review_profile(_resolve_str(data, raw_ctx, "review_profile", ""))
        affinity_key = SlotAffinityKey(
            owner_hash=_resolve_str(data, None, "owner_hash", "default"),
            chat_key=self._chat_key(data),
            backend_id=self.id,
            model=model,
            effort=effort,
            cwd_norm=norm_cwd,
            review_profile=profile,
        )
        turn_context: dict[str, Any] = {
            **(dict(raw_ctx) if raw_ctx is not None else {}),
            "model": model,
            "effort": effort,
            "review_profile": profile,
        }
        stream = self._session_manager.execute_turn_stream(
            affinity_key=affinity_key,
            prompt=self._prompt(data),
            argv_builder=self._build_argv,
            cwd=norm_cwd,
            env=self._string_mapping(data.get("env")),
            turn_context=turn_context,
            is_ephemeral=bool(data.get("is_ephemeral", False)),
        )
        raw_sink = data.get("_turn_usage_sink")
        usage_sink = raw_sink if isinstance(raw_sink, list) else None
        yield from stream_assembled_deltas(
            stream,
            usage_enabled=sample_usage_enabled(data),
            usage_sink=usage_sink,
        )

    def _build_argv(self) -> list[str]:
        if not self._cli_argv:
            raise ValueError("stdio resident cli argv is not configured")
        return self._driver.build_argv(self._cli_argv, self._options)

    @staticmethod
    def _request_mapping(request: dict[str, Any] | Any) -> Mapping[str, Any]:
        if isinstance(request, Mapping):
            return cast(Mapping[str, Any], request)
        attrs = getattr(request, "__dict__", None)
        return cast(Mapping[str, Any], attrs) if isinstance(attrs, dict) else {}

    @staticmethod
    def _chat_key(data: Mapping[str, Any]) -> str:
        for key in ("chat_key", "session_id", "conversation_id", "id"):
            val = data.get(key)
            if isinstance(val, str) and val:
                return val
        return "default"

    @staticmethod
    def _prompt(data: Mapping[str, Any]) -> str:
        prompt = data.get("prompt")
        if isinstance(prompt, str):
            return prompt
        messages = data.get("messages")
        if isinstance(messages, list):
            for msg in reversed(cast(list[object], messages)):
                m = _as_mapping(msg)
                if m is not None and isinstance(m.get("content"), str):
                    return cast(str, m["content"])
        return ""

    @staticmethod
    def _string_mapping(value: object) -> Mapping[str, str] | None:
        m = _as_mapping(value)
        if m is None:
            return None
        return {k: v for k, v in m.items() if isinstance(k, str) and isinstance(v, str)}

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

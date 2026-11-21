"""Тонкий адаптер резидентных stdio-процессов."""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import os
import shlex
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, cast, override

from core.backend_adapter import (
    ADAPTER_API as BACKEND_ADAPTER_API, SESSIONS_RESIDENT, STREAMING_NATIVE, BackendAdapter,
    BackendModel, Capabilities, KindConstraints, Qualification, StreamSink, TurnContext, TurnResult,
)
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.protocol_driver import StdioProtocolDriver
from core.stdio_resident.rpc_drivers import create_protocol_driver
from core.stdio_resident.session_manager import StdioSessionManager
from core.stdio_resident.turn_stream import TurnStreamAssembler
from core.stdio_resident.types import SlotAffinityKey
from core.stdio_resident.zero_canon_router import execute_routed_turn
from core.subbridge_zero_canon import normalize_review_profile, review_profile_from_headers

ADAPTER_API = BACKEND_ADAPTER_API
KIND = "stdio_resident"


def _empty_catalog() -> Mapping[str, Any]:
    return {}


class StdioResidentAdapter(BackendAdapter):
    """Связывает контракт адаптера с универсальным resident-ядром."""

    CONSTRAINTS: KindConstraints = KindConstraints(
        max_concurrent_max=None,
        pin_required=False,
        base_url_allowed=False,
        api_key_env_allowed=False,
        options_schema={
            "protocol": ("stream-json", "stream-jsonrpc", "acp", "msp-v1", "opencode-acp"),
            "step_dedup": ("arbiter", "off"),
        },
    )
    kind: str = KIND
    adapter_api: int = ADAPTER_API
    capabilities: Capabilities = Capabilities(
        sessions=SESSIONS_RESIDENT,
        streaming=STREAMING_NATIVE,
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
            actual_id: str = (
                str(provider_config or KIND)
                if isinstance(provider_config, str)
                else KIND
            )
        else:
            actual_id = str(backend_id)
            actual_config = dict(provider_config or {})
        super().__init__(
            actual_id, actual_config, catalog_source or _empty_catalog, host
        )
        self._has_catalog_source: bool = catalog_source is not None
        self._options: dict[str, Any] = self._extract_options(actual_config)
        from adapters.stdio_drivers import infer_protocol
        self._protocol: str = infer_protocol(actual_id, actual_config, self._options)
        self._config: StdioPoolConfig = StdioPoolConfig.from_env()
        self._pool: ResidentProcessPool = ResidentProcessPool(self._config)
        self._driver: StdioProtocolDriver = create_protocol_driver(self._protocol)
        self._session_manager: StdioSessionManager = StdioSessionManager(
            self._pool, self._driver
        )
        configured_argv = (
            cli_argv
            if cli_argv is not None
            else self._options.get(
                "cli_argv",
                self._options.get(
                    "argv",
                    actual_config.get("cli_argv", actual_config.get("wrapper")),
                ),
            )
        )
        self._cli_argv: list[str] = self._parse_argv(configured_argv)

    @staticmethod
    def _extract_options(config: Mapping[str, Any]) -> dict[str, Any]:
        bridge = config.get("bridge")
        if isinstance(bridge, Mapping):
            bridge_options = cast(Mapping[str, Any], bridge).get("options")
            if isinstance(bridge_options, Mapping):
                return dict(cast(Mapping[str, Any], bridge_options))
        options = config.get("options")
        if isinstance(options, Mapping):
            return dict(cast(Mapping[str, Any], options))
        return dict(config)

    @staticmethod
    def _parse_argv(value: object) -> list[str]:
        if isinstance(value, str):
            return shlex.split(value)
        if isinstance(value, list | tuple):
            return [str(argument) for argument in cast(Sequence[object], value)]
        return []

    def preflight_check(self) -> bool:
        """Сообщает фасаду, разрешён ли resident-путь флагом."""

        if not self._config.enabled:
            return False
        if self._protocol == "opencode-acp":
            from adapters.stdio_drivers import is_opencode_resident_enabled

            return is_opencode_resident_enabled()
        if self._protocol == "msp-v1":
            from adapters.stdio_drivers import is_resident_enabled

            return is_resident_enabled()
        return True

    def execute_chat(
        self,
        request: dict[str, Any] | Any,
        **_kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        """Выполняет ход и выдаёт OpenAI-совместимые потоковые дельты."""

        data = self._request_mapping(request)
        cwd = self._string_value(data, "cwd", os.getcwd())
        normalized_cwd = os.path.realpath(os.path.abspath(os.path.expanduser(cwd)))
        affinity_key = SlotAffinityKey(
            owner_hash=self._string_value(data, "owner_hash", "default"),
            chat_key=self._chat_key(data),
            backend_id=self.id,
            model=self._string_value(data, "model", "default"),
            effort=self._string_value(data, "effort", "medium"),
            cwd_norm=normalized_cwd,
            review_profile=normalize_review_profile(self._string_value(data, "review_profile", "")),
        )
        env = self._string_mapping(data.get("env"))
        turn_context = self._mapping_or_none(data.get("turn_context"))
        stream = self._session_manager.execute_turn_stream(
            affinity_key=affinity_key,
            prompt=self._prompt(data),
            argv_builder=self._build_argv,
            cwd=normalized_cwd,
            env=env,
            turn_context=turn_context,
            is_ephemeral=bool(data.get("is_ephemeral", False)),
        )
        assembler = TurnStreamAssembler()
        for chunk in stream:
            delta = assembler.process_chunk(chunk)
            payload: dict[str, Any] = {}
            if delta.content:
                payload["content"] = delta.content
            if delta.reasoning_content:
                payload["reasoning_content"] = delta.reasoning_content
            if delta.tool_calls:
                payload["tool_calls"] = delta.tool_calls
            finish_reason = None
            if delta.is_terminal:
                finish_reason = "tool_calls" if delta.is_tool_stop else "stop"
            yield {
                "choices": [
                    {
                        "index": 0,
                        "delta": payload,
                        "finish_reason": finish_reason,
                    }
                ]
            }

    def _build_argv(self) -> list[str]:
        if not self._cli_argv:
            raise ValueError("stdio resident cli argv is not configured")
        return self._driver.build_argv(self._cli_argv, self._options)

    @staticmethod
    def _request_mapping(request: dict[str, Any] | Any) -> Mapping[str, Any]:
        if isinstance(request, Mapping):
            return cast(Mapping[str, Any], request)
        attributes = getattr(request, "__dict__", None)
        return (
            cast(Mapping[str, Any], attributes) if isinstance(attributes, dict) else {}
        )

    @staticmethod
    def _string_value(data: Mapping[str, Any], key: str, default: str) -> str:
        value = data.get(key)
        return value if isinstance(value, str) and value else default

    @classmethod
    def _chat_key(cls, data: Mapping[str, Any]) -> str:
        for key in ("chat_key", "session_id", "conversation_id", "id"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        return "default"

    @staticmethod
    def _prompt(data: Mapping[str, Any]) -> str:
        prompt = data.get("prompt")
        if isinstance(prompt, str):
            return prompt
        messages = data.get("messages")
        if isinstance(messages, list):
            for message in reversed(cast(list[object], messages)):
                if isinstance(message, Mapping):
                    content = cast(Mapping[str, object], message).get("content")
                    if isinstance(content, str):
                        return content
        return ""

    @staticmethod
    def _mapping_or_none(value: object) -> Mapping[str, Any] | None:
        return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else None

    @staticmethod
    def _string_mapping(value: object) -> Mapping[str, str] | None:
        if not isinstance(value, Mapping):
            return None
        return {
            str(key): str(item)
            for key, item in cast(Mapping[object, object], value).items()
            if isinstance(key, str) and isinstance(item, str)
        }

    @override
    def get_models(self) -> list[BackendModel]:
        return self._catalog_models() if self._has_catalog_source else []

    @override
    def qualify(self) -> Qualification:
        enabled = self.preflight_check()
        if not enabled:
            return Qualification(False, "disabled")
        ok, reason = self._driver.verify_environment()
        return Qualification(ok, reason)

    @override
    def is_healthy(self) -> bool:
        return self.preflight_check()

    @override
    def spawn_session(self, ctx: TurnContext) -> object:
        return self._session_manager

    @override
    def execute_turn(
        self,
        ctx: TurnContext,
        sse_writer: StreamSink | None,
    ) -> TurnResult:
        raw_headers = getattr(getattr(ctx, "handler", None), "headers", None)
        request = {
            "chat_key": ctx.turn_id or ctx.rid or "default",
            "model": ctx.model,
            "effort": ctx.effort,
            "cwd": ctx.cwd or os.getcwd(),
            "prompt": ctx.prompt,
            "env": ctx.fwd_env,
            "review_profile": review_profile_from_headers(raw_headers),
        }
        hdr_map = dict(raw_headers.items()) if hasattr(raw_headers, "items") else None
        text, reasoning = execute_routed_turn(
            self.execute_chat, self._protocol, request, sse_writer, headers=hdr_map
        )
        return TurnResult(text=text, reasoning=reasoning)

    @override
    def close_session(self, sid: str) -> None:
        return None

    @override
    def shutdown(self, timeout_s: float | None = None) -> None:
        """Останавливает все дочерние процессы resident-пула."""

        self._pool.shutdown(timeout_s)

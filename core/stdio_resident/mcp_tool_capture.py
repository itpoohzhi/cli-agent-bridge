"""Домен MCP tool-capture: чистый JSON-RPC без I/O (BND-001, M-MOD-I4)."""

from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false
import hmac
import json
import secrets
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast, override

from core.tool_mode import ToolMode


@dataclass(frozen=True, slots=True)
class McpToolCaptureSpec:
    """Иммутабельная спецификация сессии (секреты скрыты, THREAT-003)."""

    nonce: str
    bearer_token: str
    tool_schemas: Mapping[str, Any]
    tool_mode: ToolMode = ToolMode.EMULATE
    server_name: str = "bridge"
    protocol_version: str = "2025-03-26"
    max_calls: int = 32

    @classmethod
    def create(
        cls, tool_schemas: Mapping[str, Any], *,
        tool_mode: ToolMode = ToolMode.EMULATE, server_name: str = "bridge",
        max_calls: int = 32,
    ) -> McpToolCaptureSpec:
        """Генерирует 128-битный nonce и 256-битный bearer token."""
        return cls(nonce=secrets.token_hex(16), bearer_token=secrets.token_hex(32),
            tool_schemas=tool_schemas, tool_mode=tool_mode, server_name=server_name,
            max_calls=max_calls)

    @property
    def capability_path(self) -> str:
        return f"/mcp/{self.nonce}"

    @override
    def __repr__(self) -> str:
        return (f"McpToolCaptureSpec(server_name={self.server_name!r}, "
            f"tool_mode={self.tool_mode!r}, nonce=<redacted>, bearer_token=<redacted>, "
            f"tools_count={len(self.tool_schemas)})")


@dataclass(frozen=True, slots=True)
class McpRpcResponse:
    """Ответ JSON-RPC метода без транспорта."""

    http_status: int
    body: dict[str, Any] | None
    captured_tool_call: bool = False


def _rpc_ok(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_err(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    """Runtime-guard: значение является Mapping, иначе None."""
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return None


def normalize_mcp_tool_name(
    raw_name: str, tool_schemas: Mapping[str, Any], server_name: str = "bridge"
) -> str:
    """Приводит имя инструмента к каноническому ключу схем."""
    if raw_name in tool_schemas:
        return raw_name
    prefixes = (f"mcp__{server_name}__", f"{server_name}__", f"{server_name}:", "mcp__bridge__", "bridge__", "bridge:")
    for prefix in prefixes:
        if raw_name.startswith(prefix):
            candidate = raw_name[len(prefix):]
            if candidate in tool_schemas or not tool_schemas:
                return candidate
    if "__" in raw_name:
        tail = raw_name.rsplit("__", 1)[-1]
        if tail in tool_schemas:
            return tail
    return raw_name


def openai_schemas_to_mcp_tools(tool_schemas: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Конвертирует OpenAI-схемы в MCP-дескрипторы tools/list."""
    tools: list[dict[str, Any]] = []
    for key, raw in tool_schemas.items():
        fn: Mapping[str, Any] = {}
        raw_map = _as_mapping(raw)
        if raw_map is not None:
            maybe_fn = _as_mapping(raw_map.get("function"))
            fn = maybe_fn if maybe_fn is not None else raw_map
        name = str(fn.get("name") or key)
        desc = str(fn.get("description") or "")
        params_map = _as_mapping(fn.get("parameters") or fn.get("inputSchema"))
        schema: dict[str, Any] = dict(params_map) if params_map is not None else {}
        if "type" not in schema:
            schema["type"] = "object"
        if not isinstance(schema.get("properties"), dict):
            schema["properties"] = {}
        tools.append({"name": name, "description": desc, "inputSchema": schema})
    return tools


def _coerce_arguments(raw_args: Any) -> dict[str, Any] | None:
    """Аргументы: dict или JSON-строка с объектом; иначе None (fail-closed)."""
    raw_map = _as_mapping(raw_args)
    if raw_map is not None:
        return dict(raw_map)
    if isinstance(raw_args, str):
        try:
            parsed: Any = json.loads(raw_args)
        except json.JSONDecodeError:
            return None
        parsed_map = _as_mapping(parsed)
        return dict(parsed_map) if parsed_map is not None else None
    return None


class McpToolCaptureSession:
    """Единственный владелец состояния перехвата (M-MOD-I4)."""

    def __init__(self, spec: McpToolCaptureSpec) -> None:
        self._spec: McpToolCaptureSpec = spec
        self._lock: threading.Lock = threading.Lock()
        self._captured_calls: list[dict[str, Any]] = []
        self._seen_methods: set[str] = set()

    @property
    def spec(self) -> McpToolCaptureSpec:
        return self._spec

    def verify_auth(self, path: str, auth_header: str | None) -> tuple[bool, int]:
        if not hmac.compare_digest(path, self._spec.capability_path):
            return (False, 403)
        if not hmac.compare_digest(auth_header or "", f"Bearer {self._spec.bearer_token}"):
            return (False, 401)
        return (True, 200)

    def handle_rpc_request(self, payload: Mapping[str, Any]) -> McpRpcResponse:
        req_id = payload.get("id")
        method = payload.get("method")
        if payload.get("jsonrpc") != "2.0" or not isinstance(method, str) or not method:
            return McpRpcResponse(200, _rpc_err(req_id, -32600, "Invalid JSON-RPC request"))
        with self._lock:
            self._seen_methods.add(method)
        if method == "initialize":
            result: dict[str, Any] = {"protocolVersion": self._spec.protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self._spec.server_name, "version": "1.0.0"}}
            return McpRpcResponse(200, _rpc_ok(req_id, result))
        if method in ("notifications/initialized", "notifications/cancelled"):
            return McpRpcResponse(202, None)
        if method == "ping":
            return McpRpcResponse(200, _rpc_ok(req_id, {}))
        if method == "tools/list":
            tools: list[dict[str, Any]] = []
            if self._spec.tool_mode is ToolMode.EMULATE:
                tools = openai_schemas_to_mcp_tools(self._spec.tool_schemas)
            return McpRpcResponse(200, _rpc_ok(req_id, {"tools": tools}))
        if method == "tools/call":
            params = _as_mapping(payload.get("params"))
            if params is None:
                return McpRpcResponse(200, _rpc_err(req_id, -32602, "invalid params"))
            return self._handle_tools_call(req_id, params)
        return McpRpcResponse(200, _rpc_err(req_id, -32601, f"method not found: {method}"))

    def _handle_tools_call(self, req_id: Any, params: Mapping[str, Any]) -> McpRpcResponse:
        if self._spec.tool_mode is not ToolMode.EMULATE:
            return McpRpcResponse(200, _rpc_err(req_id, -32001, "tool calls forbidden in current mode"))
        raw_name = params.get("name")
        if not isinstance(raw_name, str) or not raw_name:
            return McpRpcResponse(200, _rpc_err(req_id, -32602, "invalid tool name"))
        args_dict = _coerce_arguments(params.get("arguments", {}))
        if args_dict is None:
            return McpRpcResponse(200, _rpc_err(req_id, -32602, "invalid tool arguments"))
        canonical = normalize_mcp_tool_name(raw_name, self._spec.tool_schemas,
            self._spec.server_name)
        if self._spec.tool_schemas and canonical not in self._spec.tool_schemas:
            return McpRpcResponse(200, _rpc_err(req_id, -32602, f"unknown tool: {canonical}"))
        with self._lock:
            if len(self._captured_calls) >= self._spec.max_calls:
                return McpRpcResponse(200, _rpc_err(req_id, -32002, "tool capture limit exceeded"))
            idx = len(self._captured_calls)
            arguments = json.dumps(args_dict, ensure_ascii=False, separators=(",", ":"))
            self._captured_calls.append({"index": idx, "id": f"call_mcp_{idx}",
                "type": "function", "function": {"name": canonical, "arguments": arguments}})
        result = {"content": [{"type": "text", "text": "captured"}], "isError": False}
        return McpRpcResponse(200, _rpc_ok(req_id, result), captured_tool_call=True)

    def has_captured_calls(self) -> bool:
        with self._lock:
            return bool(self._captured_calls)

    def snapshot_captured_calls(self) -> list[dict[str, Any]]:
        """Независимые глубокие копии перехваченных вызовов."""
        with self._lock:
            return [json.loads(json.dumps(call)) for call in self._captured_calls]

    def seen_methods(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._seen_methods)

    def reset(self) -> None:
        with self._lock:
            self._captured_calls.clear()
            self._seen_methods.clear()

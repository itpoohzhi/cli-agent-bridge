"""Опциональный GigaRC-роутер Zero-Canon и изоляция эфемерного слота."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.runtime_env import env_bool, env_first
from core.stdio_resident.turn_error_sse import (
    DONE_FRAME,
    ResidentTurnError,
    TurnErrorResponse,
    build_turn_error,
)
from core.subbridge_zero_canon import (
    HUB_ZERO_CANON_ROUTING_FLAG,
    REVIEW_PROFILE_HEADER,
    ZERO_CANON_PROFILE,
    is_zero_canon_profile,
)
from core.timeout_ladder import FLAG_TIMEOUT_LADDER, TimeoutLadderConfig, load_timeout_ladder_config
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config

CLAUDE_BRIDGE_URL_ENV = "HUB_ZERO_CANON_CLAUDE_BRIDGE_URL"
DEFAULT_CLAUDE_BRIDGE_URL = "http://127.0.0.1:9881/v1"
CLAUDE_PROTOCOLS = frozenset({"claude-stream-json", "claude_stream_json"})
CLAUDE_BACKEND_IDS = frozenset({"claude", "claude-p", "claude_p"})
CODEX_PROTOCOLS = frozenset(
    {"codex-app-server", "codex-app-server-v2", "codex_app_server", "codex_app_server_v2"}
)
CODEX_BACKEND_IDS = frozenset({"codex", "codex-app-server", "codex-app-server-v2"})
KIND_RESIDENT, KIND_BRIDGE, KIND_EPHEMERAL = "resident", "bridge", "ephemeral"
WARM_MSP_STDIO_FLAG = "MUSE_WARM_MSP_STDIO_ENABLED"
SOCKET_HANDSHAKE_UNSUPPORTED = "MUSE_SOCKET_HANDSHAKE_UNSUPPORTED"
MUSE_TRANSPORT_EXEC, MUSE_TRANSPORT_WARM, MUSE_TRANSPORT_LEGACY = "exec", "warm_stdio", "legacy"


def decide_muse_transport(
    probe_error_code: str | None = None,
    *,
    output_schema: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Транспорт Muse (VER-009): `output_schema` — только `exec`, никогда MSP; сокет с ошибкой пробы
    (включая `MUSE_SOCKET_HANDSHAKE_UNSUPPORTED`) недоступен — при флаге warm stdio, иначе legacy.
    """
    if output_schema:
        return MUSE_TRANSPORT_EXEC
    env = os.environ if environ is None else environ
    return MUSE_TRANSPORT_WARM if env_bool(env, (WARM_MSP_STDIO_FLAG,), False) else MUSE_TRANSPORT_LEGACY


@dataclass(frozen=True, slots=True)
class ZeroCanonRoute:
    """Куда направить ход: резидентный пул, claude-p-bridge или изолированный слот."""

    kind: str
    base_url: str = ""
    is_ephemeral: bool = False


def decide_zero_canon_route(
    review_profile: str | None,
    protocol: str,
    environ: Mapping[str, str] | None = None,
    *,
    backend_id: str = "",
) -> ZeroCanonRoute:
    """Zero-Canon никогда не использует KIND_RESIDENT; Codex всегда строго KIND_EPHEMERAL."""
    if not is_zero_canon_profile(review_profile):
        return ZeroCanonRoute(KIND_RESIDENT)
    proto_norm = protocol.strip().lower()
    backend_norm = backend_id.strip().lower()
    if proto_norm in CODEX_PROTOCOLS or backend_norm in CODEX_BACKEND_IDS:
        return ZeroCanonRoute(KIND_EPHEMERAL, is_ephemeral=True)
    env = os.environ if environ is None else environ
    is_claude = proto_norm in CLAUDE_PROTOCOLS or backend_norm in CLAUDE_BACKEND_IDS
    cfg_path = resolve_hub_dynamic_config(env)
    if is_claude and read_gigarc_bool(HUB_ZERO_CANON_ROUTING_FLAG, cfg_path, environ=env, default=False):
        found = env_first(env, (CLAUDE_BRIDGE_URL_ENV,))
        return ZeroCanonRoute(KIND_BRIDGE, found[1] if found else DEFAULT_CLAUDE_BRIDGE_URL)
    return ZeroCanonRoute(KIND_EPHEMERAL, is_ephemeral=True)


class ZeroCanonIsolation:
    """Изолированный корень HOME на один ход; `active` — строго KIND_EPHEMERAL без sharing со standard."""

    def __init__(self, driver: object, root: str | None) -> None:
        self.root: str | None = root
        self.cwd: str | None = os.path.join(root, "cwd") if root is not None else None
        self._env: Callable[..., dict[str, str]] | None = getattr(driver, "build_zero_canon_env", None)
        self._argv: Callable[..., list[str]] | None = getattr(driver, "build_zero_canon_argv", None)

    @property
    def active(self) -> bool:
        return self.root is not None and callable(self._env)

    @property
    def route_kind(self) -> str:
        return KIND_EPHEMERAL if self.active else KIND_RESIDENT

    @property
    def is_ephemeral(self) -> bool:
        return self.active

    def env(self, base_env: Mapping[str, str]) -> dict[str, str] | None:
        """Изолированное окружение процесса (с проверкой отсутствия standard HOME leak) либо `None`."""
        if not self.active or self._env is None or self.root is None:
            return None
        isolated = self._env(dict(base_env), self.root)
        iso_home = str(isolated.get("HOME") or "")
        if not iso_home or not Path(iso_home).resolve().is_relative_to(Path(self.root).resolve()):
            raise RuntimeError("zero_canon_standard_home_leak")
        return isolated

    def argv(self, argv: list[str], model: str, effort: str) -> list[str]:
        """Zero-Canon argv драйвера, если изоляция активна."""
        if not self.active or not callable(self._argv):
            return argv
        return self._argv(argv, model=model, effort=effort)


@contextmanager
def zero_canon_isolation(driver: Any, review_profile: str | None) -> Iterator[ZeroCanonIsolation]:
    """Создаёт одноразовый корень `zc-*` (0700) и гарантированно удаляет его.

    Fail-closed: если запрошен Zero-Canon, а драйвер не реализует `build_zero_canon_env`,
    поднимает `RuntimeError` вместо молчаливого обхода изоляции.
    """
    if not is_zero_canon_profile(review_profile):
        yield ZeroCanonIsolation(driver, None)
        return
    if not callable(getattr(driver, "build_zero_canon_env", None)):
        raise RuntimeError(f"zero_canon_unsupported_by_driver:{type(driver).__name__}")
    root = tempfile.mkdtemp(prefix="zc-")
    try:
        os.chmod(root, 0o700)
        cwd_dir = os.path.join(root, "cwd")
        os.makedirs(cwd_dir, mode=0o700, exist_ok=True)
        os.chmod(cwd_dir, 0o700)
        yield ZeroCanonIsolation(driver, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise urllib.error.HTTPError(newurl, code, f"redirect blocked ({msg})", headers, fp)


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _validate_loopback_bridge_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in _LOOPBACK_HOSTS:
        raise ValueError(f"non_loopback_zero_canon_bridge_url:{base_url}")
    return base_url.rstrip("/")


def _resolve_proxy_timeout_s(
    timeout_s: float | None, environ: Mapping[str, str] | None = None
) -> float:
    if timeout_s is not None:
        return timeout_s
    env = os.environ if environ is None else environ
    raw = env.get("HUB_ZERO_CANON_PROXY_TIMEOUT_S")
    if raw is not None and raw.strip():
        return float(raw)
    try:
        ladder = load_timeout_ladder_config(env)
    except ValueError:
        if env_bool(env, (FLAG_TIMEOUT_LADDER,), False):
            raise
        ladder = TimeoutLadderConfig()
    return ladder.effective_first_event_s if ladder.enabled else 180.0


def proxy_zero_canon_bridge_turn(
    base_url: str,
    model: str,
    prompt: str,
    headers: Mapping[str, str] | None = None,
    *,
    timeout_s: float | None = None,
) -> tuple[str, str]:
    """Перенаправляет Zero-Canon Claude-ход на локальный loopback claude-p-bridge (`:9881`)."""
    effective_timeout = _resolve_proxy_timeout_s(timeout_s)
    url = _validate_loopback_bridge_url(base_url) + "/chat/completions"
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    req_headers: dict[str, str] = {
        "Content-Type": "application/json",
        REVIEW_PROFILE_HEADER: ZERO_CANON_PROFILE,
    }
    if headers:
        for key, value in headers.items():
            if key.lower() == "x-subagent-id" and value:
                req_headers["X-Subagent-Id"] = value
    bridge_key = os.environ.get("CLAUDE_P_BRIDGE_KEY") or os.environ.get("CLAUDE_BRIDGE_KEY") or ""
    if bridge_key:
        req_headers["Authorization"] = f"Bearer {bridge_key}"
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler())
    with opener.open(req, timeout=effective_timeout) as resp:
        parsed = json.loads(resp.read().decode("utf-8"))
    choices = parsed.get("choices") if isinstance(parsed, dict) else None
    if not isinstance(choices, list) or not choices:
        return "", ""
    msg = choices[0].get("message") if isinstance(choices[0], dict) else {}
    if not isinstance(msg, dict):
        return "", ""
    return str(msg.get("content") or ""), str(msg.get("reasoning_content") or "")


def _build_routed_turn_error(exc: BaseException, live_sent: int) -> TurnErrorResponse:
    if isinstance(exc, RuntimeError) and str(exc).startswith("zero_canon_unsupported_by_driver:"):
        status = 503 if not live_sent else 200
        error_type = "zero_canon_unsupported"
        code = "zero_canon_unsupported_by_driver"
        message = str(exc)[:500]
        body: dict[str, object] = {"error": {"message": message, "type": error_type, "code": code}}
        sse = "data: " + json.dumps(body, ensure_ascii=False) + "\n\n" + DONE_FRAME
        return TurnErrorResponse(
            status=status, error_type=error_type, code=code, message=message, sse=sse, body=body
        )
    return build_turn_error(exc, live_sent=live_sent)


def _stream_bridge_chunks(
    route: ZeroCanonRoute,
    request: dict[str, Any],
    headers: Mapping[str, str] | None,
) -> Iterator[tuple[str, str]]:
    content, thought = proxy_zero_canon_bridge_turn(
        route.base_url,
        str(request.get("model") or "default"),
        str(request.get("prompt") or ""),
        headers,
    )
    if content:
        yield "content", content
    if thought:
        yield "reasoning_content", thought


def _stream_routed_chunks(
    execute_chat: Callable[[dict[str, Any]], Iterator[dict[str, Any]]],
    route: ZeroCanonRoute,
    request: dict[str, Any],
    headers: Mapping[str, str] | None,
) -> Iterator[tuple[str, str]]:
    if route.kind == KIND_BRIDGE:
        yield from _stream_bridge_chunks(route, request, headers)
        return
    if is_zero_canon_profile(str(request.get("review_profile") or "")) and route.kind == KIND_RESIDENT:
        raise RuntimeError("zero_canon_resident_route_forbidden")
    routed_req = {**request, "is_ephemeral": bool(request.get("is_ephemeral")) or route.is_ephemeral}
    for chunk in execute_chat(routed_req):
        delta = chunk["choices"][0]["delta"]
        if isinstance(content := delta.get("content"), str):
            yield "content", content
        if isinstance(thought := delta.get("reasoning_content"), str):
            yield "reasoning_content", thought


def execute_routed_turn(
    execute_chat: Callable[[dict[str, Any]], Iterator[dict[str, Any]]],
    protocol: str,
    request: dict[str, Any],
    sse_writer: Callable[[str, str], Any] | None,
    *,
    headers: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Выполняет ход с учётом `decide_zero_canon_route` и `build_turn_error`."""
    route = decide_zero_canon_route(
        str(request.get("review_profile") or ""), protocol, backend_id=str(request.get("backend_id") or "")
    )
    parts: dict[str, list[str]] = {"content": [], "reasoning_content": []}
    live_sent = 0
    try:
        for kind, value in _stream_routed_chunks(execute_chat, route, request, headers):
            parts[kind].append(value)
            if sse_writer is not None:
                live_sent += 1
                _ = sse_writer(kind, value)
    except Exception as exc:
        err = _build_routed_turn_error(exc, live_sent)
        raise ResidentTurnError(err) from exc
    return "".join(parts["content"]), "".join(parts["reasoning_content"])

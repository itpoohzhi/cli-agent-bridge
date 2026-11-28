"""Опциональный GigaRC-роутер Zero-Canon и изоляция эфемерного слота."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.runtime_env import env_bool, env_first
from core.session_plane.zc_env_guard import (
    allocate_zc_slot_home,
    is_zero_canon_keyed_resident_enabled,
    verify_zc_slot_home,
)
from core.stdio_resident.bridge_proxy_payload import BridgeProxyOptions as BridgeProxyOptions
from core.stdio_resident.proxy_policy import (
    NoRedirectHandler as _NoRedirectHandler,  # noqa: F401
    ensure_loopback_url as _validate_loopback_bridge_url,
    resolve_proxy_timeout_s as _resolve_proxy_timeout_s,
)
from core.stdio_resident.routed_turn_result import (
    ProxyBridgeOptions,
    RoutedExecOptions,
    RoutedTurnResult,
    build_routed_turn_error as _build_routed_turn_error,  # noqa: F401
    execute_routed_turn_result as _execute_routed_turn_result_impl,
    proxy_zero_canon_bridge_turn_result as _proxy_result_impl,
)
from core.stdio_resident.turn_error_sse import (
    DONE_FRAME as DONE_FRAME,
    ResidentTurnError as ResidentTurnError,
    TurnErrorResponse as TurnErrorResponse,
    build_turn_error as build_turn_error,
)
from core.subbridge_zero_canon import (
    HUB_ZERO_CANON_ROUTING_FLAG,
    REVIEW_PROFILE_HEADER as REVIEW_PROFILE_HEADER,
    ZERO_CANON_PROFILE as ZERO_CANON_PROFILE,
    is_zero_canon_profile,
)
from core.zc_static_cwd_and_source import (
    CODEX_BACKEND_IDS as CODEX_BACKEND_IDS,
    CODEX_PROTOCOLS as CODEX_PROTOCOLS,
    resolve_zero_canon_cwd,
)
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config, sanitize_zero_canon_env

CLAUDE_BRIDGE_URL_ENV = "HUB_ZERO_CANON_CLAUDE_BRIDGE_URL"
DEFAULT_CLAUDE_BRIDGE_URL = "http://127.0.0.1:9881/v1"
CLAUDE_PROTOCOLS = frozenset({"claude-stream-json", "claude_stream_json"})
CLAUDE_BACKEND_IDS = frozenset({"claude", "claude-p", "claude_p"})
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
    ephemeral_identity: bool = True,
) -> ZeroCanonRoute:
    """Zero-Canon не использует KIND_RESIDENT, кроме keyed-режима (kill-switch ON и `ephemeral_identity=False`).

    Keyed-резидентный маршрут сохраняет полную Zero-Canon изоляцию (`zero_canon_isolation`); Codex иначе —
    строго KIND_EPHEMERAL.
    """
    if not is_zero_canon_profile(review_profile):
        return ZeroCanonRoute(KIND_RESIDENT)
    proto_norm = protocol.strip().lower()
    backend_norm = backend_id.strip().lower()
    keyed = not ephemeral_identity and is_zero_canon_keyed_resident_enabled(environ)
    if proto_norm in CODEX_PROTOCOLS or backend_norm in CODEX_BACKEND_IDS:
        return ZeroCanonRoute(KIND_RESIDENT) if keyed else ZeroCanonRoute(KIND_EPHEMERAL, is_ephemeral=True)
    env = os.environ if environ is None else environ
    is_claude = proto_norm in CLAUDE_PROTOCOLS or backend_norm in CLAUDE_BACKEND_IDS
    cfg_path = resolve_hub_dynamic_config(env)
    if is_claude and read_gigarc_bool(HUB_ZERO_CANON_ROUTING_FLAG, cfg_path, environ=env, default=False):
        found = env_first(env, (CLAUDE_BRIDGE_URL_ENV,))
        return ZeroCanonRoute(KIND_BRIDGE, found[1] if found else DEFAULT_CLAUDE_BRIDGE_URL)
    return ZeroCanonRoute(KIND_RESIDENT) if keyed else ZeroCanonRoute(KIND_EPHEMERAL, is_ephemeral=True)


class ZeroCanonIsolation:
    """Изолированный корень HOME; `active` — Zero-Canon изоляция без sharing со standard.

    `persist=True` (keyed warm-слот): корень живёт пока жив слот, а не один ход.
    """

    def __init__(self, driver: object, root: str | None, *, cwd: str | None = None, persist: bool = False) -> None:
        self.root: str | None = root
        self.persist: bool = persist
        self.cwd: str | None = (
            cwd if cwd is not None else (resolve_zero_canon_cwd(driver, root) if root is not None else None)
        )
        self._env: Callable[..., dict[str, str]] | None = getattr(driver, "build_zero_canon_env", None)
        self._argv: Callable[..., list[str]] | None = getattr(driver, "build_zero_canon_argv", None)

    @property
    def active(self) -> bool:
        return self.root is not None and callable(self._env)

    @property
    def route_kind(self) -> str:
        return KIND_RESIDENT if (not self.active or self.persist) else KIND_EPHEMERAL

    @property
    def is_ephemeral(self) -> bool:
        return self.active and not self.persist

    def env(self, base_env: Mapping[str, str]) -> dict[str, str] | None:
        """Изолированное окружение процесса (с проверкой отсутствия standard HOME leak) либо `None`."""
        if not self.active or self._env is None or self.root is None:
            return None
        isolated = self._persisted_env(base_env) if self.persist else None
        if isolated is None:
            isolated = self._env(dict(base_env), self.root)
        iso_home = str(isolated.get("HOME") or "")
        if not iso_home or not Path(iso_home).resolve().is_relative_to(Path(self.root).resolve()):
            raise RuntimeError("zero_canon_standard_home_leak")
        return isolated

    def _persisted_env(self, base_env: Mapping[str, str]) -> dict[str, str] | None:
        """Повторный ход в уже подготовленном keyed-HOME: без перезаписи файлов (`O_EXCL`); грязный HOME → fail-closed."""
        root = Path(str(self.root))
        if not (root / ".codex" / "config.toml").exists():
            return None
        if not verify_zc_slot_home(root)[0]:
            raise RuntimeError("zero_canon_dirty_home")
        cleaned = sanitize_zero_canon_env(base_env, root)
        cleaned["CODEX_HOME"] = str(root / ".codex")
        cleaned["BRIDGE_ZERO_CANON"] = "1"
        return cleaned

    def argv(self, argv: list[str], model: str, effort: str) -> list[str]:
        """Zero-Canon argv драйвера, если изоляция активна."""
        if not self.active or not callable(self._argv):
            return argv
        return self._argv(argv, model=model, effort=effort)


def _keyed_zc_root(keyed_slot_id: str) -> str:
    """Стабильный 0700 каталог `.../zc-<id>/home/zc-<id>` (basename `zc-*` требует `_verify_zc_clean_home`)."""
    slug = hashlib.sha256(keyed_slot_id.encode("utf-8")).hexdigest()[:32]
    root = allocate_zc_slot_home(f"zc-{slug}") / f"zc-{slug}"
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    return str(root)


@contextmanager
def zero_canon_isolation(
    driver: Any, review_profile: str | None, *, keyed_slot_id: str = "", persist: bool = False
) -> Iterator[ZeroCanonIsolation]:
    """Создаёт корень `zc-*` (0700); одноразовый — удаляется в `finally`, keyed (`persist`) — живёт со слотом.

    Fail-closed: если запрошен Zero-Canon, а драйвер не реализует `build_zero_canon_env`,
    поднимает `RuntimeError` вместо молчаливого обхода изоляции. Keyed-корень удаляет `ResidentProcessPool`.
    """
    if not is_zero_canon_profile(review_profile):
        yield ZeroCanonIsolation(driver, None)
        return
    if not callable(getattr(driver, "build_zero_canon_env", None)):
        raise RuntimeError(f"zero_canon_unsupported_by_driver:{type(driver).__name__}")
    keyed = bool(persist and keyed_slot_id)
    root = _keyed_zc_root(keyed_slot_id) if keyed else tempfile.mkdtemp(prefix="zc-")
    try:
        os.chmod(root, 0o700)
        cwd_dir = resolve_zero_canon_cwd(driver, root)
        if cwd_dir == os.path.join(root, "cwd"):
            os.makedirs(cwd_dir, mode=0o700, exist_ok=True)
            os.chmod(cwd_dir, 0o700)
        yield ZeroCanonIsolation(driver, root, cwd=cwd_dir, persist=keyed)
    finally:
        if not keyed:
            shutil.rmtree(root, ignore_errors=True)


def _proxy_opts(**kw: Any) -> ProxyBridgeOptions:
    return ProxyBridgeOptions(
        validate_url_fn=_validate_loopback_bridge_url, resolve_timeout_fn=_resolve_proxy_timeout_s,
        opener_factory=urllib.request.build_opener, timeout_s=kw.get("timeout_s"),
        usage_enabled=bool(kw.get("usage_enabled", True)),
        proxy_options=kw.get("proxy_options"), sse_writer=kw.get("sse_writer"),
    )


def proxy_zero_canon_bridge_turn_result(
    base_url: str, model: str, prompt: str, headers: Mapping[str, str] | None = None, **kwargs: Any,
) -> RoutedTurnResult:
    """Перенаправляет Zero-Canon Claude-ход на локальный `:9881` с сохранением TurnUsage."""
    return _proxy_result_impl(base_url, model, prompt, headers, _proxy_opts(**kwargs))


def proxy_zero_canon_bridge_turn(
    base_url: str, model: str, prompt: str, headers: Mapping[str, str] | None = None, *, timeout_s: float | None = None,
) -> tuple[str, str]:
    """Legacy-обёртка над `proxy_zero_canon_bridge_turn_result` (возвращает `(text, reasoning)`)."""
    res = proxy_zero_canon_bridge_turn_result(base_url, model, prompt, headers, timeout_s=timeout_s)
    return res.text, res.reasoning


_DEFAULT_PROXY_TURN = proxy_zero_canon_bridge_turn


def _bridge_proxy_compat(
    base_url: str, model: str, prompt: str, headers: Mapping[str, str] | None = None, **kwargs: Any,
) -> RoutedTurnResult:
    if proxy_zero_canon_bridge_turn is _DEFAULT_PROXY_TURN:
        return _proxy_result_impl(base_url, model, prompt, headers, _proxy_opts(**kwargs))
    content, thought = proxy_zero_canon_bridge_turn(base_url, model, prompt, headers)
    return RoutedTurnResult(content, thought, None)


def execute_routed_turn_result(
    execute_chat: Callable[[dict[str, Any]], Iterator[dict[str, Any]]],
    protocol: str,
    request: dict[str, Any],
    sse_writer: Callable[[str, str], Any] | None,
    **kwargs: Any,
) -> RoutedTurnResult:
    """Выполняет ход с учётом `decide_zero_canon_route`, возвращая `RoutedTurnResult`."""
    route = decide_zero_canon_route(
        str(request.get("review_profile") or ""),
        protocol,
        backend_id=str(request.get("backend_id") or ""),
    )
    raw_enabled = request.get("_usage_enabled")
    usage_enabled = raw_enabled if isinstance(raw_enabled, bool) else True
    opts = RoutedExecOptions(
        bridge_proxy_fn=_bridge_proxy_compat,
        headers=kwargs.get("headers"),
        usage_enabled=usage_enabled,
        proxy_options=kwargs.get("proxy_options"),
    )
    return _execute_routed_turn_result_impl(execute_chat, route, request, sse_writer, opts)


def execute_routed_turn(
    execute_chat: Callable[[dict[str, Any]], Iterator[dict[str, Any]]],
    protocol: str,
    request: dict[str, Any],
    sse_writer: Callable[[str, str], Any] | None,
    *,
    headers: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Legacy-обёртка над `execute_routed_turn_result` (возвращает `(text, reasoning)`)."""
    res = execute_routed_turn_result(
        execute_chat, protocol, request, sse_writer, headers=headers
    )
    return res.text, res.reasoning

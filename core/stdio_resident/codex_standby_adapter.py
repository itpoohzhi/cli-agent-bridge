"""Тонкий Codex-адаптер demand-driven warm standby pool (AD-003, AD-005, BND-003).

Warm-слот = процесс `codex app-server` после ТОЛЬКО `initialize` handshake (никакого `thread/start`/промпта до claim).
Zero-Canon слот живёт в чистом `zc-codex-*` HOME (0o700) с allowlisted env без ключей хоста.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass

from core.resident_turn_envelope import ResidentTurnEnvelope
from core.stdio_resident.codex_driver import CodexAppServerV2Driver
from core.stdio_resident.demand_standby_pool import DemandStandbyPool
from core.stdio_resident.process_io import ResidentProcessHandle
from core.stdio_resident.process_reaper import get_pgid_rss_bytes, terminate_process_group
from core.stdio_resident.runtime_types import ResidentTurnOptions
from core.stdio_resident.standby_pool_fsm import ProfileKey, WarmSlotHandle, parse_limits
from core.stdio_resident.zero_canon_router import ZeroCanonIsolation
from core.zc_static_cwd_and_source import is_codex_driver, resolve_zero_canon_cwd

_LOGGER = logging.getLogger(__name__)
_BACKEND_ID = "codex"
_ZC_PREFIX = "zc-codex-"
_BASE_ARGV = ("codex", "app-server")
_MIB = 1024 * 1024
_pool_lock = threading.Lock()
_pool: DemandStandbyPool | None = None


@dataclass
class CodexWarmHandle:
    handle: ResidentProcessHandle
    profile: ProfileKey
    driver: CodexAppServerV2Driver
    zc_home_root: str = ""
    cwd: str = ""
    pgid: int = 0


def _warm(handle: WarmSlotHandle) -> CodexWarmHandle:
    if not isinstance(handle, CodexWarmHandle):
        raise TypeError("codex_standby_foreign_handle")
    return handle


_ZC_ENV_EXACT = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "TERM", "LANG", "TZ", "TMPDIR",
    "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy",
    "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CODEX_HOME",
})
_ZC_ENV_PREFIXES = ("LC_", "CODEX_")


def _filter_zc_env(raw: Mapping[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in raw.items()
        if (k in _ZC_ENV_EXACT or k.startswith(_ZC_ENV_PREFIXES)) and not k.endswith(("_BRIDGE_KEY", "_SERVICE_KEY"))
    }


def _rm_zc_home(root: str) -> None:
    if root and os.path.basename(os.path.normpath(root)).startswith(_ZC_PREFIX):
        shutil.rmtree(root, ignore_errors=True)


class CodexStandbyAdapter:
    """`StandbyAdapter`: spawn_warm/is_alive/claim/dispose/rss_mb без доступа к `DemandStandbyPool._slots`."""

    def __init__(
        self,
        *,
        argv_factory: Callable[[ProfileKey], list[str]] | None = None,
        base_env_provider: Callable[[], Mapping[str, str]] | None = None,
        driver_factory: Callable[[], CodexAppServerV2Driver] | None = None,
    ) -> None:
        self._argv_factory: Callable[[ProfileKey], list[str]] | None = argv_factory
        self._base_env: Callable[[], Mapping[str, str]] = base_env_provider or (lambda: os.environ)
        self._driver_factory: Callable[[], CodexAppServerV2Driver] = driver_factory or CodexAppServerV2Driver

    def _argv(self, profile: ProfileKey, driver: CodexAppServerV2Driver) -> list[str]:
        if self._argv_factory is not None:
            return list(self._argv_factory(profile))
        argv: list[str] = list(_BASE_ARGV)
        return driver.build_zero_canon_argv(argv, profile.model, profile.effort) if profile.is_zero_canon else argv

    def _prepare(self, profile: ProfileKey, driver: CodexAppServerV2Driver) -> tuple[dict[str, str], str, str]:
        """Возвращает (env, cwd, zc_home_root); при ошибке подготовки чистит созданный HOME."""
        base_env = dict(self._base_env())
        if not profile.is_zero_canon:
            return base_env, tempfile.gettempdir(), ""
        root = tempfile.mkdtemp(prefix=_ZC_PREFIX)
        try:
            os.chmod(root, 0o700)
            env = driver.build_zero_canon_env(_filter_zc_env(base_env), root)
            return env, resolve_zero_canon_cwd(driver, root), root
        except BaseException:
            _rm_zc_home(root)
            raise

    def spawn_warm(self, profile: ProfileKey, *, timeout_s: float = 30.0) -> CodexWarmHandle:
        driver = self._driver_factory()
        env, cwd, root = self._prepare(profile, driver)
        warm: CodexWarmHandle | None = None
        try:
            proc = ResidentProcessHandle.spawn(self._argv(profile, driver), cwd, env)
            warm = CodexWarmHandle(proc, profile, driver, root, cwd, proc.pid)
            if not driver.run_handshake(proc, timeout_s=timeout_s) or not proc.is_alive():
                raise RuntimeError("codex_standby_handshake_failed")
        except Exception as exc:
            if warm is not None:
                self.dispose(warm)
            else:
                _rm_zc_home(root)
            if str(exc) == "codex_standby_handshake_failed":
                raise
            raise RuntimeError("codex_standby_handshake_failed") from exc
        return warm

    def is_alive(self, handle: WarmSlotHandle) -> bool:
        return _warm(handle).handle.is_alive()

    def claim(self, handle: WarmSlotHandle) -> CodexWarmHandle:
        warm = _warm(handle)
        if not warm.handle.is_alive():
            raise RuntimeError("codex_standby_dead")
        return warm

    def dispose(self, handle: WarmSlotHandle) -> None:
        """Идемпотентно: гасит PGID и удаляет `zc-codex-*` HOME."""
        warm = _warm(handle)
        try:
            _ = warm.handle.terminate_gracefully(grace_s=2.0)
        except Exception:
            with suppress(Exception):
                _ = terminate_process_group(warm.handle.proc, warm.pgid or warm.handle.pid, "", cancel_grace_s=0.0)
        _rm_zc_home(warm.zc_home_root)

    def rss_mb(self, handle: WarmSlotHandle) -> float:
        warm = _warm(handle)
        rss = get_pgid_rss_bytes(warm.pgid or warm.handle.pid)
        return 0.0 if rss is None else rss / _MIB


def get_codex_standby_pool() -> DemandStandbyPool:
    """Ленивый синглтон пула (создаётся только при включённом флаге)."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = DemandStandbyPool({_BACKEND_ID: CodexStandbyAdapter()})
        return _pool


def set_codex_standby_pool(pool: DemandStandbyPool | None) -> DemandStandbyPool | None:
    """Подмена синглтона (тесты/shutdown); возвращает прежний пул."""
    global _pool
    with _pool_lock:
        old, _pool = _pool, pool
    return old


def codex_standby_profile(envelope: ResidentTurnEnvelope, iso: ZeroCanonIsolation) -> ProfileKey:
    cwd_class = "zc-static" if iso.active else "std"
    return ProfileKey(_BACKEND_ID, envelope.model, envelope.effort, envelope.review_profile, envelope.env_digest, cwd_class)


def maybe_run_codex_standby_hook(
    driver: object, envelope: ResidentTurnEnvelope, iso: ZeroCanonIsolation, options: ResidentTurnOptions
) -> None:
    """Тонкий хук `ResidentBridgeRuntime`: сигнал demand для будущего warm-слота (fire-and-forget).

    `enabled=False` (env `BRIDGE_DEMAND_STANDBY_ENABLED`) или не-Codex драйвер — мгновенный возврат без создания пула.
    Любая ошибка проглатывается: standby не должен влиять на ход.
    """
    _ = options
    if not parse_limits(os.environ, None).enabled or not is_codex_driver(driver):
        return
    try:
        get_codex_standby_pool().submit_demand(codex_standby_profile(envelope, iso))
    except Exception as exc:
        _LOGGER.warning("codex standby demand failed err=%s", type(exc).__name__)

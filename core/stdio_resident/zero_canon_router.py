"""Опциональный GigaRC-роутер Zero-Canon и изоляция эфемерного слота."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from core.runtime_env import env_bool, env_first
from core.subbridge_zero_canon import HUB_ZERO_CANON_ROUTING_FLAG, is_zero_canon_profile

CLAUDE_BRIDGE_URL_ENV = "HUB_ZERO_CANON_CLAUDE_BRIDGE_URL"
DEFAULT_CLAUDE_BRIDGE_URL = "http://127.0.0.1:9881/v1"
CLAUDE_PROTOCOLS = frozenset({"claude-stream-json", "claude_stream_json"})
KIND_RESIDENT, KIND_BRIDGE, KIND_EPHEMERAL = "resident", "bridge", "ephemeral"


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
) -> ZeroCanonRoute:
    """Zero-Canon не смешивается с резидентным пулом; мост :9881 — только по флагу.

    `HUB_ZERO_CANON_ROUTING_ENABLED` (дефолт `False`) включает перенаправление Claude
    на claude-p-bridge; без флага Zero-Canon идёт в изолированный ephemeral слот.
    """
    if not is_zero_canon_profile(review_profile):
        return ZeroCanonRoute(KIND_RESIDENT)
    env = os.environ if environ is None else environ
    if protocol in CLAUDE_PROTOCOLS and env_bool(env, (HUB_ZERO_CANON_ROUTING_FLAG,), False):
        found = env_first(env, (CLAUDE_BRIDGE_URL_ENV,))
        return ZeroCanonRoute(KIND_BRIDGE, found[1] if found else DEFAULT_CLAUDE_BRIDGE_URL)
    return ZeroCanonRoute(KIND_EPHEMERAL, is_ephemeral=True)


class ZeroCanonIsolation:
    """Изолированный корень HOME на один ход; `active` — драйвер поддерживает Zero-Canon."""

    def __init__(self, driver: object, root: str | None) -> None:
        self.root = root
        self._env: Callable[..., dict[str, str]] | None = getattr(driver, "build_zero_canon_env", None)
        self._argv: Callable[..., list[str]] | None = getattr(driver, "build_zero_canon_argv", None)

    @property
    def active(self) -> bool:
        return self.root is not None and callable(self._env)

    def env(self, base_env: Mapping[str, str]) -> dict[str, str] | None:
        """Изолированное окружение процесса либо `None`, если изоляция неактивна."""
        if not self.active or self._env is None or self.root is None:
            return None
        return self._env(dict(base_env), self.root)

    def argv(self, argv: list[str], model: str, effort: str) -> list[str]:
        """Zero-Canon argv драйвера, если изоляция активна."""
        if not self.active or not callable(self._argv):
            return argv
        return self._argv(argv, model=model, effort=effort)


@contextmanager
def zero_canon_isolation(driver: Any, review_profile: str | None) -> Iterator[ZeroCanonIsolation]:
    """Создаёт одноразовый корень `zc-*` (0700) и гарантированно удаляет его."""
    if not is_zero_canon_profile(review_profile) or not callable(
        getattr(driver, "build_zero_canon_env", None)
    ):
        yield ZeroCanonIsolation(driver, None)
        return
    root = tempfile.mkdtemp(prefix="zc-")
    os.chmod(root, 0o700)
    try:
        yield ZeroCanonIsolation(driver, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

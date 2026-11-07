"""Флаги и пути загрузки каталога моделей (слой A/B, дефолт `false` = прежнее поведение).

Флаги читаются через `core.runtime_env.flag_enabled` (снимок GigaRC, fallback env, дефолт
`false`). Модуль не знает имён вендоров: allowlist базовых URL берётся из сайдкара
`catalog-lock/1`, путь каталога — из состояния (`BRIDGE_STATE_DIR`).

Флаги:
- `BRIDGE_FLEET_SAFE_CATALOG_ENABLED` — `build_catalog(mode="isolate")`;
- `BRIDGE_PROVIDER_CONSTRAINTS_ENABLED` — `KindConstraints` адаптеров + allowlist из сайдкара;
- `BRIDGE_COMPILED_FLEET_ENABLED` — читать `state/fleet.compiled.json`, если он валиден;
- `BRIDGE_QUARANTINE_GATE_ENABLED` — ролевой карантинный гейт `core.quarantine_gate` в `server.py`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from core.backend_adapter import AllowEntry, FleetViolation, build_catalog
from core.quarantine_gate import SidecarView
from core.runtime_env import flag_enabled

FLAG_SAFE_CATALOG = "BRIDGE_FLEET_SAFE_CATALOG_ENABLED"
FLAG_PROVIDER_CONSTRAINTS = "BRIDGE_PROVIDER_CONSTRAINTS_ENABLED"
FLAG_COMPILED_FLEET = "BRIDGE_COMPILED_FLEET_ENABLED"
FLAG_QUARANTINE_GATE = "BRIDGE_QUARANTINE_GATE_ENABLED"
DEFAULT_STATE_DIR = "~/work/cli-agent-bridge/state"
COMPILED_FLEET_FILE = "fleet.compiled.json"
SIDECAR_FILE = "catalog.lock.json"


@dataclass(frozen=True)
class CatalogFlags:
    """Снимок флагов загрузки каталога (читается один раз на загрузку)."""

    safe_catalog: bool = False
    provider_constraints: bool = False
    compiled_fleet: bool = False


def catalog_flags(
    reader: Callable[[str], bool] = flag_enabled,
) -> CatalogFlags:
    """Текущие значения флагов; любой сбой чтения — `false` (прежнее поведение)."""

    def _read(name: str) -> bool:
        try:
            return bool(reader(name))
        except Exception:  # noqa: BLE001 - флаги не должны ронять загрузку каталога
            return False

    return CatalogFlags(
        _read(FLAG_SAFE_CATALOG),
        _read(FLAG_PROVIDER_CONSTRAINTS),
        _read(FLAG_COMPILED_FLEET),
    )


def state_dir(env: Optional[Mapping[str, str]] = None) -> Path:
    source = os.environ if env is None else env
    return Path(os.path.expanduser(source.get("BRIDGE_STATE_DIR") or DEFAULT_STATE_DIR))


def quarantine_gate_enabled(reader: Callable[[str], bool] = flag_enabled) -> bool:
    """Флаг ролевого карантинного гейта; сбой чтения — `false` (безопасный rollout, ADR-0015)."""
    try:
        return bool(reader(FLAG_QUARANTINE_GATE))
    except Exception:  # noqa: BLE001 - флаг не должен ронять обработку запроса
        return False


def sidecar_path(env: Optional[Mapping[str, str]] = None) -> Path:
    """Путь сайдкара: `BRIDGE_CATALOG_LOCK` или `<state>/catalog.lock.json`."""
    source = os.environ if env is None else env
    return Path(
        os.path.expanduser(source.get("BRIDGE_CATALOG_LOCK") or "")
        or str(state_dir(source) / SIDECAR_FILE)
    )


_SIDECAR_CACHE: Dict[str, Tuple[Tuple[int, int], SidecarView]] = {}


def load_sidecar_view(env: Optional[Mapping[str, str]] = None) -> SidecarView:
    """Сайдкар для гейта с кэшем по (mtime_ns, size). Нет файла — пустое представление.

    Битый файл — `ValueError`/`OSError` (решает вызывающий, fail-closed для gated-ролей).
    """
    path = sidecar_path(env)
    try:
        st = path.stat()
    except FileNotFoundError:
        return SidecarView({})
    sig = (st.st_mtime_ns, st.st_size)
    hit = _SIDECAR_CACHE.get(str(path))
    if hit is not None and hit[0] == sig:
        return hit[1]
    view = SidecarView.from_path(path)
    _SIDECAR_CACHE[str(path)] = (sig, view)
    return view


def sidecar_allowlist(
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Dict[str, Tuple[AllowEntry, ...]]]:
    """`allow_base_url` провайдеров из сайдкара; нет сайдкара или он битый — `None`."""
    path = sidecar_path(env)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        providers: Mapping[str, Any] = data["providers"]
        result: Dict[str, Tuple[AllowEntry, ...]] = {}
        for pid, entry in providers.items():
            result[pid] = tuple(
                AllowEntry(
                    str(item["scheme"]),
                    str(item["host"]),
                    int(item["port"]),
                    str(item.get("path_prefix", "/v1")),
                )
                for item in entry.get("allow_base_url", [])
            )
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def compiled_fleet_valid(path: Path, kinds: Mapping[str, Any]) -> bool:
    """Скомпилированный каталог читается и проходит `build_catalog(strict)`."""
    try:
        build_catalog(json.loads(path.read_text(encoding="utf-8")), kinds)
    except (OSError, ValueError, FleetViolation):
        return False
    return True


def resolve_fleet_path(
    default: Path,
    kinds: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    compiled_enabled: Optional[bool] = None,
) -> Path:
    """Путь каталога: явный `DROID_DSH_BRIDGE_FLEET` > скомпилированный (флаг) > `default`."""
    source = os.environ if env is None else env
    explicit = source.get("DROID_DSH_BRIDGE_FLEET", "")
    if explicit:
        return Path(explicit)
    enabled = (
        catalog_flags().compiled_fleet if compiled_enabled is None else compiled_enabled
    )
    if enabled:
        compiled = state_dir(source) / COMPILED_FLEET_FILE
        if compiled_fleet_valid(compiled, kinds):
            return compiled
    return default

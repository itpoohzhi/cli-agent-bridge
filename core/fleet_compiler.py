"""Компилятор каталога: `providers.d/*.yaml` + `_fleet.yaml` -> `fleet.json` schema 3 (слой B).

Pure-ядро `compile_catalog` не читает диск и не использует время/random: одинаковые входы
дают побайтно одинаковый `fleet.json`. `compile_fleet` — удобная обёртка с загрузкой
манифестов с диска. Вся аттестация моделей (status, family, quota_group, efforts_proven,
ссылки на квитанции) живёт в сайдкаре `catalog-lock/1`; ключи `fleet.json` schema 3 не
расширяются (`FLEET_TOP_KEYS`/`FLEET_MODEL_KEYS` не меняются).

Алгоритм (спецификация §4.4.1):
1. `backends.<id>` строится из `transport.bridge` манифеста (для raw-HTTP шва к нему
   добавляются upstream-параметры из `transport.direct.http`: `api_key_ref`,
   `headers_from_json`, `per_request_headers`, `default_body_extra`); провайдеры без bridge
   (direct-only) попадают только в сайдкар.
2. Модели провайдера = `models_overrides ∪ discovery.static ∪ discovery.model_ids`.
   Поля: `models_overrides` ⊕ discovery.meta ⊕ `models_defaults`; для `confirmed`/`stale` с
   валидной квитанцией efforts берутся из `efforts_proven`.
3. Один `model_id` у нескольких провайдеров: при явном routing побеждает максимальный вес
   enabled bridge, затем `(priority, provider_id)`; без routing сохраняется прежний выбор.
4. Каждая модель проверяется `build_catalog(strict)` на синтетическом каталоге из одной
   модели: провал -> `rejected[mid]`, в `fleet` модель не попадает.
5. Порядок детерминирован: провайдеры по `(priority, provider_id)`, модели по `model_id`.
6. Self-check: итог проходит `build_catalog(strict, constraints_enabled=False)`; провал —
   `CompileError`, ничего не записывается.

`quorum_eligible` вычисляет только компилятор (QT-3); ручное значение в overrides
игнорируется с предупреждением.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Unpack

from core.backend_adapter import FleetViolation, build_catalog
from core.backend_params import extract_backend_params
from core.compile_model_records import CompileOptions, CompileResult, model_record as model_record
from core.compile_routes_pipeline import compile_catalog as _compile_catalog
from core.compile_routes_pipeline import render_fleet_json as _render_fleet_json
from core.model_lifecycle import (
    LifecycleRegistry,
)
from core.provider_manifest import (
    ManifestError,
    ProviderManifest,
    failover_backend_entry,
    load_manifests,
    providers_dir,
    read_yaml_file,
)

COMPILER_VERSION = 1
SIDECAR_SCHEMA = "catalog-lock/1"
HEADER_KEYS = (
    "schema_version",
    "catalogue",
    "aliases",
    "default_model",
    "policy_ref",
    "technical_ref",
    "image_limits",
    "admission",
)
HEADER_REQUIRED = ("schema_version", "default_model", "image_limits", "admission")
MODEL_KEY_ORDER = (
    "id",
    "backend",
    "name",
    "efforts",
    "default_effort",
    "context_window",
    "max_tokens",
    "input",
    "images",
    "policy_lines",
)
# Ключи override, которые копируются в запись fleet.json как есть (после MODEL_KEY_ORDER).
_OVERRIDE_EXTRA_KEYS = ("upstream_model", "resident", "pool_size", "alias_of")
_QUORUM_FAMILY_SOURCES = ("exact_map", "owned_by", "prefix")
DEFAULT_IMAGES = {
    "cli_registry": "",
    "status": "unverified",
    "method": None,
    "proof": None,
}


class CompileError(Exception):
    """Фатальная ошибка компиляции (шапка, self-check); `slug` — причина класса I."""

    def __init__(self, slug: str, model: str = "-") -> None:
        super().__init__(slug)
        self.slug = slug
        self.model = model


# ---- канонический вывод -------------------------------------------------------------


def canonical_json(obj: Any) -> bytes:
    """Канонический JSON (sorted keys) для хэшей и сайдкара."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def render_fleet_json(fleet: Mapping[str, Any]) -> bytes:
    """Делегирует канонический многострочный вывод UTF-8 с завершающим LF."""
    return _render_fleet_json(fleet)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- шапка --------------------------------------------------------------------------


def validate_header(header: Any) -> Dict[str, Any]:
    """Проверяет `_fleet.yaml`; возвращает копию с ключами в каноническом порядке."""
    if not isinstance(header, Mapping):
        raise CompileError("header_invalid")
    unknown = set(header) - set(HEADER_KEYS)
    if unknown:
        raise CompileError("header_key_unknown")
    if header.get("schema_version") != 3 or isinstance(
        header.get("schema_version"), bool
    ):
        raise CompileError("schema_version_invalid")
    for key in HEADER_REQUIRED:
        if key not in header:
            raise CompileError("header_invalid")
    return {key: header[key] for key in HEADER_KEYS if key in header}


# ---- сборка записей -----------------------------------------------------------------


def _upstream_params(manifest: ProviderManifest) -> Dict[str, Any]:
    """Upstream-параметры raw-HTTP шва из `transport.direct.http` и `params` манифеста.

    Нужны, когда провайдер ходит через мост (`transport.bridge.base_url`), но upstream требует
    ключ/заголовки из пользовательских файлов. Ссылки на файлы не читаются при компиляции:
    значения резолвит адаптер на каждом запросе, поэтому `fleet.json` остаётся детерминированным.
    """
    bridge = manifest.transport.bridge
    direct = manifest.transport.direct
    http = direct.http if direct is not None else None
    if bridge is None or bridge.base_url is None or not http:
        return {}
    out: Dict[str, Any] = {}
    ref = http.get("api_key_ref")
    if isinstance(ref, str) and ref.startswith("file:"):
        out["api_key_ref"] = ref
    elif isinstance(ref, Mapping):
        fallback = ref.get("fallback_file")
        if isinstance(fallback, str) and fallback:
            out["api_key_ref"] = "file:" + fallback
    headers = http.get("headers_from_json")
    if isinstance(headers, Mapping):
        path = headers.get("path")
        key = headers.get("key")
        pick = headers.get("pick") or headers.get("required")
        if isinstance(path, str) and isinstance(key, str) and isinstance(pick, list):
            out["headers_from_json"] = {
                "file": path,
                "json_path": key.split("."),
                "pick": [str(name) for name in pick],
            }
    per_request = http.get("per_request_headers")
    if isinstance(per_request, Mapping) and per_request:
        out["per_request_headers"] = {str(k): str(v) for k, v in per_request.items()}
    default_off = manifest.params.effort_map.get("off")
    rules = manifest.models_overrides
    # Тело запроса общее для всех моделей провайдера, поэтому «выключено» подставляется
    # только когда его просит каждая модель: иначе дефолт одной модели глушил бы другую.
    if (
        isinstance(default_off, Mapping)
        and default_off
        and rules
        and all(rule.fields.get("default_effort") == "off" for rule in rules)
    ):
        out["default_body_extra"] = json.loads(json.dumps(default_off))
    return out


def backend_entry(manifest: ProviderManifest) -> Dict[str, Any]:
    """Запись `backends.<id>` fleet.json из манифеста (`transport.bridge` обязателен)."""
    bridge = manifest.transport.bridge
    if bridge is None:
        raise CompileError("provider_bridge_missing", manifest.provider_id)
    entry: Dict[str, Any] = {
        "kind": manifest.kind,
        "enabled": manifest.enabled,
        "required": manifest.required,
        "owned_by": manifest.owned_by,
        "max_concurrent": manifest.limits.max_concurrent,
    }
    if bridge.base_url is not None:
        entry["base_url"] = bridge.base_url
    if bridge.api_key_env is not None:
        entry["api_key_env"] = bridge.api_key_env
    if bridge.wrapper is not None:
        entry["wrapper"] = bridge.wrapper
    fingerprint = manifest.fingerprint
    if fingerprint.binary_path and fingerprint.binary_sha256:
        ref: Dict[str, Any] = {}
        if fingerprint.version is not None:
            ref["version"] = fingerprint.version
        ref["binary_sha256"] = fingerprint.binary_sha256
        ref["binary_path"] = fingerprint.binary_path
        entry["technical_ref"] = ref
    if bridge.options:
        entry["options"] = dict(bridge.options)
    if bridge.proxy_port is not None:
        entry["proxy_port"] = bridge.proxy_port
    if bridge.idle_timeout_s is not None:
        entry["idle_timeout_s"] = bridge.idle_timeout_s
    if bridge.safety_cap_s is not None:
        entry["safety_cap_s"] = bridge.safety_cap_s
    for part in (failover_backend_entry(getattr(manifest, "failover", None)), _upstream_params(manifest), extract_backend_params(manifest)):
        entry.update(part)
    return entry


def _model_ids(manifest: ProviderManifest, discovered: Sequence[str]) -> List[str]:
    ids = {rule.model_id for rule in manifest.models_overrides}
    ids.update(manifest.discovery.static)
    ids.update(discovered)
    return sorted(ids)


def _intersect(first: Sequence[str], second: Optional[Sequence[str]]) -> List[str]:
    if second is None:
        return list(first)
    allowed = set(second)
    return [item for item in first if item in allowed]


def _receipt_efforts(
    receipt: Mapping[str, Any], efforts_pin: Optional[Sequence[str]]
) -> Tuple[List[str], str]:
    proven = receipt.get("efforts_proven")
    if not isinstance(proven, list):
        return [], ""
    efforts = _intersect([str(e) for e in proven], efforts_pin)
    default = str(receipt.get("default_effort") or "")
    if default not in efforts and efforts:
        default = efforts[-1]
    return efforts, default


def _check_single(
    header: Mapping[str, Any],
    manifest: ProviderManifest,
    record: Mapping[str, Any],
    kinds: Mapping[str, Any],
) -> str:
    """Пустая строка — запись проходит `build_catalog(strict)`; иначе slug причины."""
    entry = backend_entry(manifest)
    entry["enabled"] = True
    synthetic = {
        "schema_version": 3,
        "catalogue": header.get("catalogue", ""),
        "default_model": record["id"],
        "image_limits": header["image_limits"],
        "admission": header["admission"],
        "backends": {manifest.provider_id: entry},
        "models": [dict(record)],
    }
    try:
        build_catalog(synthetic, kinds, mode="strict", image_probe=False)
    except FleetViolation as violation:
        return violation.reason
    return ""


def _allow_dicts(manifest: ProviderManifest) -> List[Dict[str, Any]]:
    return [
        {
            "scheme": entry.scheme,
            "host": entry.host,
            "port": entry.port,
            "path_prefix": entry.path_prefix,
        }
        for entry in manifest.allow_base_url
    ]


def _direct_dict(manifest: ProviderManifest) -> Optional[Dict[str, Any]]:
    direct = manifest.transport.direct
    if direct is None:
        return None
    result: Dict[str, Any] = {"type": direct.type}
    if direct.cli is not None:
        result.update(
            executables=list(direct.cli.executables),
            argv_by_executable={
                k: list(v) for k, v in direct.cli.argv_by_executable.items()
            },
            prompt_via=direct.cli.prompt_via,
            output=dict(direct.cli.output),
        )
    if direct.http is not None:
        result["http"] = dict(direct.http)
    return result


def _provider_sidecar(manifest: ProviderManifest, fingerprint: str) -> Dict[str, Any]:
    params = manifest.params
    entry: Dict[str, Any] = {
        "kind": manifest.kind,
        "enabled": manifest.enabled,
        "quota_group": manifest.limits.quota_group,
        "max_concurrent": manifest.limits.max_concurrent,
        "timeout_s": manifest.limits.timeout_s,
        "fingerprint_sha256": fingerprint,
        "allow_base_url": _allow_dicts(manifest),
        "bridge": manifest.transport.bridge is not None,
        "params": {
            "effort_field": params.effort_field,
            "effort_map": dict(params.effort_map),
            "adaptive_whitelist": list(params.adaptive_whitelist),
            "strip_always": list(params.strip_always),
            "tool_emulation": params.tool_emulation,
        },
        "probe": {
            "enabled": manifest.probe.enabled,
            "max_parallel": manifest.probe.max_parallel,
        },
    }
    direct = _direct_dict(manifest)
    if direct is not None:
        entry["direct"] = direct
    return entry


def _history_max(env: Optional[Mapping[str, str]]) -> int:
    source = os.environ if env is None else env
    try:
        return max(1, int(source.get("BRIDGE_CATALOG_HISTORY_MAX", "20")))
    except ValueError:
        return 20


# Делегирует компиляцию с совместимыми фабриками фасада.
def compile_catalog(header: Mapping[str, Any], manifests: Sequence[ProviderManifest], *,
    kinds: Mapping[str, Any], **options: Unpack[CompileOptions]) -> CompileResult:
    options["error_factory"] = CompileError
    options["result_factory"] = _compiled_result
    return _compile_catalog(header, manifests, kinds=kinds, **options)


def _compiled_result(
    fleet: Dict[str, Any],
    sidecar: Dict[str, Any],
    rejected: Mapping[str, str],
    warnings: Tuple[str, ...],
    rejected_providers: Mapping[str, Tuple[str, ...]],
) -> CompileResult:
    """Привязывает sidecar к байтам публичного renderer, сохраняя legacy-тип результата."""
    sidecar = dict(sidecar, fleet_sha256=sha256_hex(render_fleet_json(fleet)))
    return CompileResult(fleet, sidecar, rejected, warnings, rejected_providers)


def _ordered_model_ids(
    models: Mapping[str, Any],
    owner: Mapping[str, str],
    ordered: Sequence[ProviderManifest],
) -> List[str]:
    """Провайдеры по `(priority, provider_id)`, внутри — по `model_id`."""
    out: List[str] = []
    for manifest in ordered:
        out.extend(
            sorted(mid for mid in models if owner.get(mid) == manifest.provider_id)
        )
    return out


# ---- обёртки с диском ---------------------------------------------------------------


def default_kinds() -> Mapping[str, Any]:
    """Реестр видов, заданный в коде (`adapters.ADAPTER_KINDS`); импорт ленивый."""
    from adapters import ADAPTER_KINDS

    return ADAPTER_KINDS


def load_header(path: Path) -> Dict[str, Any]:
    try:
        raw = read_yaml_file(path)
    except ManifestError as exc:
        raise CompileError("header_unreadable") from exc
    return validate_header(raw)


def compile_from_disk(
    providers_path: Optional[Path] = None,
    fleet_meta_path: Optional[Path] = None,
    *,
    kinds: Optional[Mapping[str, Any]] = None,
    discovery: Optional[Mapping[str, Any]] = None,
    registry: Optional[LifecycleRegistry] = None,
    receipts: Optional[Mapping[str, Mapping[str, Any]]] = None,
    now: str = "",
    env: Optional[Mapping[str, str]] = None,
) -> CompileResult:
    """Загружает манифесты и шапку с диска и компилирует каталог."""
    base = Path(providers_path) if providers_path else providers_dir(env)
    meta = Path(fleet_meta_path) if fleet_meta_path else base / "_fleet.yaml"
    registry_kinds = kinds if kinds is not None else default_kinds()
    loaded = load_manifests(base, registry_kinds, env=env)
    digests = dict(loaded.sha256_by_file)
    if meta.is_file():
        digests[meta.name] = sha256_hex(meta.read_bytes())
    return compile_catalog(
        load_header(meta),
        loaded.manifests,
        kinds=registry_kinds,
        discovery=discovery,
        registry=registry,
        receipts=receipts,
        rejected_providers=loaded.rejected_providers,
        manifest_digests=digests,
        now=now,
        env=env,
    )


def compile_fleet(
    providers_path: Optional[Path] = None,
    fleet_meta_path: Optional[Path] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """`providers.d` + шапка -> словарь формата `fleet.json` (schema 3)."""
    return compile_from_disk(providers_path, fleet_meta_path, **kwargs).fleet


def load_receipts(probes_path: Path) -> Dict[str, Dict[str, Any]]:
    """Квитанции пробника `<sha>.json`: берутся только те, где sha256(байт) == имени файла."""
    receipts: Dict[str, Dict[str, Any]] = {}
    if not Path(probes_path).is_dir():
        return receipts
    for path in sorted(Path(probes_path).glob("*.json")):
        try:
            raw = path.read_bytes()
            doc = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            continue
        if sha256_hex(raw) == path.stem and isinstance(doc, dict):
            receipts[path.stem] = doc
    return receipts


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Атомарная запись: `tmp` в том же каталоге -> fsync -> `os.replace`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

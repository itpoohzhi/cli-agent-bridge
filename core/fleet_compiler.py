"""Компилятор каталога: `providers.d/*.yaml` + `_fleet.yaml` -> `fleet.json` schema 3 (слой B).

Pure-ядро `compile_catalog` не читает диск и не использует время/random: одинаковые входы
дают побайтно одинаковый `fleet.json`. `compile_fleet` — удобная обёртка с загрузкой
манифестов с диска. Вся аттестация моделей (status, family, quota_group, efforts_proven,
ссылки на квитанции) живёт в сайдкаре `catalog-lock/1`; ключи `fleet.json` schema 3 не
расширяются (`FLEET_TOP_KEYS`/`FLEET_MODEL_KEYS` не меняются).

Алгоритм (спецификация §4.4.1):
1. `backends.<id>` строится из `transport.bridge` манифеста; провайдеры без bridge
   (direct-only) попадают только в сайдкар.
2. Модели провайдера = `models_overrides ∪ discovery.static ∪ discovery.model_ids`.
   Поля: `models_overrides` ⊕ discovery.meta ⊕ `models_defaults`; для `confirmed`/`stale` с
   валидной квитанцией efforts берутся из `efforts_proven`.
3. Один `model_id` у нескольких провайдеров: побеждает минимальный `(priority, provider_id)`,
   остальные — в `alternates` сайдкара.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.backend_adapter import FleetViolation, build_catalog
from core.model_lifecycle import (
    STATUS_CONFIRMED,
    STATUS_QUARANTINE,
    STATUS_STALE,
    LifecycleRegistry,
)
from core.provider_manifest import (
    ManifestError,
    ProviderManifest,
    load_manifests,
    providers_dir,
    read_yaml_file,
    resolve_family,
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


@dataclass(frozen=True)
class CompileResult:
    """Итог компиляции: `fleet` (schema 3), `sidecar` (catalog-lock/1), диагностика."""

    fleet: Dict[str, Any]
    sidecar: Dict[str, Any]
    rejected: Mapping[str, str] = field(default_factory=dict)
    warnings: Tuple[str, ...] = ()
    rejected_providers: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)


# ---- канонический вывод -------------------------------------------------------------


def canonical_json(obj: Any) -> bytes:
    """Канонический JSON (sorted keys) для хэшей и сайдкара."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def render_fleet_json(fleet: Mapping[str, Any]) -> bytes:
    """Байты `fleet.json`: порядок ключей сохраняется, отступ 2, UTF-8, завершающий `\\n`."""
    return (json.dumps(fleet, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


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


def model_record(
    manifest: ProviderManifest,
    model_id: str,
    meta: Mapping[str, Any],
    receipt: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Запись модели schema 3: overrides ⊕ discovery.meta ⊕ models_defaults."""
    rule = manifest.rule_for(model_id)
    override: Mapping[str, Any] = rule.fields if rule else {}
    defaults = manifest.models_defaults
    efforts = list(override.get("efforts") or defaults.efforts)
    default_effort = str(override.get("default_effort") or defaults.default_effort)
    if receipt is not None:
        proven, proven_default = _receipt_efforts(
            receipt, rule.efforts_pin if rule else None
        )
        if proven:
            efforts, default_effort = proven, proven_default
    record: Dict[str, Any] = {
        "id": model_id,
        "backend": manifest.provider_id,
        "name": str(override.get("name") or model_id),
        "efforts": efforts,
        "default_effort": default_effort,
        "context_window": override.get(
            "context_window", meta.get("context_window", defaults.context_window)
        ),
        "max_tokens": override.get(
            "max_tokens", meta.get("max_tokens", defaults.max_tokens)
        ),
        "input": list(override.get("input") or ["text"]),
        "images": dict(override.get("images") or DEFAULT_IMAGES),
    }
    if override.get("policy_lines"):
        record["policy_lines"] = list(override["policy_lines"])
    for key in _OVERRIDE_EXTRA_KEYS:
        if override.get(key) is not None:
            record[key] = override[key]
    return record


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


def compile_catalog(
    header: Mapping[str, Any],
    manifests: Sequence[ProviderManifest],
    *,
    kinds: Mapping[str, Any],
    discovery: Optional[Mapping[str, Any]] = None,
    registry: Optional[LifecycleRegistry] = None,
    receipts: Optional[Mapping[str, Mapping[str, Any]]] = None,
    rejected_providers: Optional[Mapping[str, Tuple[str, ...]]] = None,
    manifest_digests: Optional[Mapping[str, str]] = None,
    now: str = "",
    env: Optional[Mapping[str, str]] = None,
) -> CompileResult:
    """Pure-компиляция каталога; `now` — строка времени сайдкара (не влияет на `fleet`)."""
    clean_header = validate_header(header)
    discovery = discovery or {}
    receipts = receipts or {}
    history_max = _history_max(env)
    ordered = sorted(manifests, key=lambda m: (m.priority, m.provider_id))
    rejected: Dict[str, str] = {}
    rejected_by: Dict[str, str] = {}
    warnings: List[str] = []
    bad_providers: Dict[str, Tuple[str, ...]] = dict(rejected_providers or {})

    backends: Dict[str, Any] = {}
    fingerprints: Dict[str, str] = {}
    for manifest in ordered:
        found = discovery.get(manifest.provider_id)
        fingerprints[manifest.provider_id] = (
            getattr(found, "fingerprint_sha256", "") if found is not None else ""
        )
        if manifest.transport.bridge is None:
            continue
        entry = backend_entry(manifest)
        probe_entry = dict(entry, enabled=True)
        synthetic = {
            "schema_version": 3,
            "default_model": "-",
            "image_limits": clean_header["image_limits"],
            "admission": clean_header["admission"],
            "backends": {manifest.provider_id: probe_entry},
            "models": [],
        }
        try:
            build_catalog(synthetic, kinds, mode="strict")
        except FleetViolation as violation:
            if violation.reason not in ("models_invalid", "default_model_invalid"):
                bad_providers[manifest.provider_id] = (violation.reason,)
                continue
        backends[manifest.provider_id] = entry

    fleet_models: Dict[str, Dict[str, Any]] = {}
    fleet_owner: Dict[str, str] = {}
    candidates: Dict[
        str, List[Tuple[ProviderManifest, Dict[str, Any], Mapping[str, Any]]]
    ] = {}
    for manifest in ordered:
        if manifest.provider_id in bad_providers:
            continue
        found = discovery.get(manifest.provider_id)
        discovered = list(getattr(found, "model_ids", ()) or ())
        meta_map: Mapping[str, Mapping[str, Any]] = getattr(found, "meta", {}) or {}
        for model_id in _model_ids(manifest, discovered):
            rule = manifest.rule_for(model_id)
            if rule is not None and "quorum_eligible" in rule.fields:
                warnings.append(f"quorum_eligible_override_ignored:{model_id}")
            candidates.setdefault(model_id, []).append(
                (manifest, dict(meta_map.get(model_id, {})), {})
            )

    sidecar_models: Dict[str, Dict[str, Any]] = {}
    for model_id in sorted(candidates):
        providers = candidates[model_id]
        bridged = [item for item in providers if item[0].transport.bridge is not None]
        serving = [item for item in providers if item[0].enabled]
        primary = (serving or providers)[0][0]
        fleet_source = bridged[0] if bridged else None
        alternates = [
            {"provider": item[0].provider_id}
            for item in providers
            if item[0].provider_id != primary.provider_id
        ]
        status_owner = primary
        fp = fingerprints.get(status_owner.provider_id, "")
        record = (
            registry.get((status_owner.provider_id, model_id, fp)) if registry else None
        )
        status = record.status if record is not None else STATUS_QUARANTINE
        receipt = None
        if (
            record is not None
            and status in (STATUS_CONFIRMED, STATUS_STALE)
            and record.receipt_sha256
        ):
            candidate = receipts.get(record.receipt_sha256)
            if (
                isinstance(candidate, Mapping)
                and candidate.get("verdict") == "confirmed"
            ):
                receipt = candidate
            elif status == STATUS_CONFIRMED:
                status = STATUS_QUARANTINE
        elif status == STATUS_CONFIRMED:
            status = STATUS_QUARANTINE
        if fleet_source is not None:
            manifest, meta, _ = fleet_source
            fleet_record = model_record(
                manifest, model_id, meta, receipt if manifest is status_owner else None
            )
            reason = _check_single(clean_header, manifest, fleet_record, kinds)
            if reason:
                rejected[model_id] = reason
                rejected_by[model_id] = manifest.provider_id
                continue
            fleet_models[model_id] = fleet_record
            fleet_owner[model_id] = manifest.provider_id
        family, family_source = resolve_family(status_owner, model_id)
        quorum = bool(
            status == STATUS_CONFIRMED
            and family
            and family_source in _QUORUM_FAMILY_SOURCES
        )
        entry: Dict[str, Any] = {
            "provider": status_owner.provider_id,
            "status": status,
            "family": family,
            "family_source": family_source,
            "quorum_eligible": quorum,
            "quota_group": status_owner.limits.quota_group,
            "in_fleet": fleet_source is not None,
            "efforts_proven": list(receipt.get("efforts_proven") or [])
            if receipt
            else [],
            "alternates": alternates,
            "history": [dict(h) for h in (record.history if record else ())][
                -history_max:
            ],
        }
        if receipt is not None and record is not None:
            entry["probe"] = {
                "receipt_sha256": record.receipt_sha256,
                "fingerprint_sha256": record.fingerprint_sha256,
                "probe_version": receipt.get("probe_version"),
                "at": receipt.get("finished_at"),
            }
        sidecar_models[model_id] = entry

    fleet: Dict[str, Any] = dict(clean_header)
    fleet["backends"] = backends
    fleet["models"] = [
        fleet_models[mid]
        for mid in _ordered_model_ids(fleet_models, fleet_owner, ordered)
        if mid in fleet_models
    ]
    try:
        build_catalog(fleet, kinds, mode="strict", constraints_enabled=False)
    except FleetViolation as violation:
        raise CompileError(violation.reason, violation.model) from violation
    fleet_bytes = render_fleet_json(fleet)

    digests = dict(manifest_digests or {})
    discovery_digest = sha256_hex(
        canonical_json(
            {
                pid: {
                    "fingerprint_sha256": getattr(found, "fingerprint_sha256", ""),
                    "model_ids": list(getattr(found, "model_ids", ()) or ()),
                }
                for pid, found in sorted(discovery.items())
            }
        )
    )
    sidecar: Dict[str, Any] = {
        "schema": SIDECAR_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "compiled_at": now,
        "inputs": {
            "manifests": digests,
            "manifests_sha256": sha256_hex(canonical_json(digests)),
            "discovery_sha256": discovery_digest,
        },
        "fleet_sha256": sha256_hex(fleet_bytes),
        "providers": {
            m.provider_id: _provider_sidecar(m, fingerprints.get(m.provider_id, ""))
            for m in ordered
            if m.provider_id not in bad_providers
        },
        "models": sidecar_models,
        "rejected": {
            mid: {"provider": rejected_by.get(mid, ""), "reason": reason}
            for mid, reason in sorted(rejected.items())
        },
        "rejected_providers": {
            pid: list(r) for pid, r in sorted(bad_providers.items())
        },
    }
    return CompileResult(
        fleet=fleet,
        sidecar=sidecar,
        rejected=dict(rejected),
        warnings=tuple(warnings),
        rejected_providers=bad_providers,
    )


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

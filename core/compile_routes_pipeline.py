"""Поэтапная детерминированная компиляция каталога транспортов."""

from __future__ import annotations

import hashlib
import json  # Точные legacy bytes: indent=2 с LF и компактный канон хэшей без LF.
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, TypeAlias, Unpack

from core import compile_model_records as records
from core.backend_adapter import FleetViolation, build_catalog
from core.catalog_routes import compile_model_routing, provider_route, provider_routing
from core.routing_schema import RoutingDocument, route_owner_key

Candidate: TypeAlias = tuple[records.ManifestLike, Mapping[str, Any]]

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


class PipelineOptions(records.CompileOptions, total=False):
    """Наследует параметры и совместимые фабрики из общего контракта."""


@dataclass
class CompileState:
    """Изолированное состояние одного холодного прохода компилятора."""

    header: dict[str, Any]
    ordered: Sequence[records.ManifestLike]
    kinds: Mapping[str, Any]
    options: PipelineOptions
    backends: dict[str, Any] = field(default_factory=dict)
    fingerprints: dict[str, str] = field(default_factory=dict)
    candidates: dict[str, list[Candidate]] = field(default_factory=dict)
    models: dict[str, dict[str, Any]] = field(default_factory=dict)
    owners: dict[str, str] = field(default_factory=dict)
    sidecar_models: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)
    rejected_by: dict[str, str] = field(default_factory=dict)
    bad_providers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def canonical_json(value: object) -> bytes:
    """Сохраняет точный UTF-8 канон существующих хэшей."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def render_fleet_json(fleet: Mapping[str, Any]) -> bytes:
    """Сохраняет порядок ключей, legacy-отступ и завершающий LF."""
    return (json.dumps(fleet, indent=2, ensure_ascii=False) + "\n").encode()


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _header(header: Mapping[str, Any], options: PipelineOptions) -> dict[str, Any]:
    error = options.get("error_factory", records.CompileError)
    if not isinstance(header, Mapping):
        raise error("header_invalid", "-")
    if set(header) - set(HEADER_KEYS):
        raise error("header_key_unknown", "-")
    if header.get("schema_version") != 3 or isinstance(
        header.get("schema_version"), bool
    ):
        raise error("schema_version_invalid", "-")
    if any(key not in header for key in HEADER_REQUIRED):
        raise error("header_invalid", "-")
    return {key: header[key] for key in HEADER_KEYS if key in header}


def _check(state: CompileState, backends: Mapping[str, Any], models: list[Any]) -> str:
    synthetic = dict(state.header, backends=dict(backends), models=models)
    synthetic["default_model"] = models[0]["id"] if models else "-"
    try:
        build_catalog(synthetic, state.kinds, mode="strict", image_probe=False)
    except FleetViolation as violation:
        return violation.reason
    return ""


def _collect(state: CompileState) -> None:
    discovery = state.options.get("discovery") or {}
    for manifest in state.ordered:
        pid = manifest.provider_id
        found = discovery.get(pid)
        state.fingerprints[pid] = getattr(found, "fingerprint_sha256", "")
        if pid in state.bad_providers:
            continue
        if manifest.transport.bridge is not None:
            entry = records.backend_entry(manifest)
            reason = _check(state, {pid: dict(entry, enabled=True)}, [])
            if reason not in ("", "models_invalid", "default_model_invalid"):
                state.bad_providers[pid] = (reason,)
                continue
            state.backends[pid] = entry
        _collect_models(state, manifest, found)


def _collect_models(
    state: CompileState, manifest: records.ManifestLike, found: object
) -> None:
    ids = set(getattr(found, "model_ids", ()) or ())
    ids.update(manifest.discovery.static)
    ids.update(rule.model_id for rule in manifest.models_overrides)
    meta = getattr(found, "meta", {}) or {}
    for model_id in sorted(ids):
        rule = manifest.rule_for(model_id)
        if rule and "quorum_eligible" in rule.fields:
            state.warnings.append(f"quorum_eligible_override_ignored:{model_id}")
        state.candidates.setdefault(model_id, []).append(
            (manifest, meta.get(model_id, {}))
        )


def _history_max(options: records.CompileOptions) -> int:
    env = options.get("env")
    source = os.environ if env is None else env
    try:
        return max(1, int(source.get("BRIDGE_CATALOG_HISTORY_MAX", "20")))
    except ValueError:
        return 20


def _weighted_source(
    enabled: list[Candidate], model_id: str | None = None
) -> Candidate | None:
    """Выбирает владельца независимо от сериализации singleton routing."""
    if enabled and any(
        provider_routing(p, model_id).weight is not None for p, _ in enabled
    ):
        return min(
            enabled,
            key=lambda item: route_owner_key(provider_route(item[0], model_id)),
        )
    return None


def _select(
    providers: list[Candidate],
    model_id: str | None = None,
) -> tuple[records.ManifestLike, Candidate | None, RoutingDocument | None]:
    bridged = sorted(
        (item for item in providers if item[0].transport.bridge is not None),
        key=lambda item: (
            provider_route(item[0], model_id)["priority"],
            item[0].provider_id,
        ),
    )
    primary = next((p for p, _ in providers if p.enabled), providers[0][0])
    enabled = [item for item in bridged if item[0].enabled]
    fleet_source = next(iter(enabled), next(iter(bridged), None))
    weighted = _weighted_source(enabled, model_id)
    routing = None
    if weighted is not None:
        fleet_source = weighted
        primary = fleet_source[0]
        if len(enabled) > 1:
            routing = compile_model_routing(
                [provider for provider, _ in enabled],
                bridged[0][0].provider_id,
                model_id=model_id,
            )
    return primary, fleet_source, routing


def _compile_model(state: CompileState, model_id: str, history_max: int) -> None:
    providers = state.candidates[model_id]
    owner, fleet_source, routing = _select(providers, model_id)
    proof = records.model_proof(
        owner, model_id, state.fingerprints[owner.provider_id], state.options
    )
    if fleet_source is not None:
        manifest, meta = fleet_source
        record = records.model_record(
            manifest, model_id, meta, proof.receipt if manifest is owner else None
        )
        backend = dict(state.backends[manifest.provider_id], enabled=True)
        reason = _check(state, {manifest.provider_id: backend}, [record])
        if reason:
            state.rejected[model_id] = reason
            state.rejected_by[model_id] = manifest.provider_id
            return
        if routing is not None:
            record["routing"] = routing
        state.models[model_id] = record
        state.owners[model_id] = manifest.provider_id
    alternates = [{"provider": p.provider_id} for p, _ in providers if p is not owner]
    entry = records.model_sidecar(owner, model_id, proof, alternates, history_max)
    entry["in_fleet"] = fleet_source is not None
    state.sidecar_models[model_id] = entry


def _fleet(state: CompileState) -> dict[str, Any]:
    models = [
        state.models[mid]
        for provider in state.ordered
        for mid in sorted(state.models)
        if state.owners[mid] == provider.provider_id
    ]
    fleet = dict(state.header, backends=state.backends, models=models)
    try:
        build_catalog(fleet, state.kinds, mode="strict", constraints_enabled=False)
    except FleetViolation as violation:
        error = state.options.get("error_factory", records.CompileError)
        raise error(violation.reason, violation.model) from violation
    return fleet


def _provider_sidecar(
    manifest: records.ManifestLike, fingerprint: str
) -> dict[str, Any]:
    limits = asdict(manifest.limits)
    limits.pop("pin_required")
    entry: dict[str, Any] = {
        "kind": manifest.kind,
        "enabled": manifest.enabled,
        **limits,
        "allow_base_url": [asdict(allow) for allow in manifest.allow_base_url],
        "bridge": manifest.transport.bridge is not None,
    }
    if fingerprint:
        entry["fingerprint_sha256"] = fingerprint
    direct = manifest.transport.direct
    if direct is not None:
        direct_entry: dict[str, Any] = {"type": direct.type}
        if direct.cli is not None:
            direct_entry.update(asdict(direct.cli))
        if direct.http is not None:
            direct_entry["http"] = dict(direct.http)
        entry["direct"] = direct_entry
    # Dataclass tuple-поля снаружи, как и прежде, представлены JSON-массивами.
    return json.loads(canonical_json(entry))


def _sidecar(state: CompileState, fleet: Mapping[str, Any]) -> dict[str, Any]:
    digests = dict(state.options.get("manifest_digests") or {})
    discovery = {
        pid: {
            "fingerprint_sha256": getattr(found, "fingerprint_sha256", ""),
            "model_ids": list(getattr(found, "model_ids", ()) or ()),
        }
        for pid, found in sorted((state.options.get("discovery") or {}).items())
    }
    return {
        "schema": "catalog-lock/1",
        "compiler_version": 1,
        "compiled_at": state.options.get("now", ""),
        "inputs": {
            "manifests": digests,
            "manifests_sha256": _digest(digests),
            "discovery_sha256": _digest(discovery),
        },
        "fleet_sha256": hashlib.sha256(render_fleet_json(fleet)).hexdigest(),
        "providers": {
            p.provider_id: _provider_sidecar(p, state.fingerprints[p.provider_id])
            for p in state.ordered
            if p.provider_id not in state.bad_providers
        },
        "models": state.sidecar_models,
        "rejected": {
            mid: {"provider": state.rejected_by[mid], "reason": reason}
            for mid, reason in sorted(state.rejected.items())
        },
        "rejected_providers": {
            pid: list(reasons) for pid, reasons in sorted(state.bad_providers.items())
        },
    }


def compile_catalog(
    header: Mapping[str, Any],
    manifests: Sequence[records.ManifestLike],
    *,
    kinds: Mapping[str, Any],
    **options: Unpack[PipelineOptions],
) -> records.CompileResult:
    """Компилирует без I/O; legacy-фасад может передать свои фабрики типов."""
    ordered = sorted(
        manifests, key=lambda manifest: (manifest.priority, manifest.provider_id)
    )
    state = CompileState(_header(header, options), ordered, kinds, options)
    state.bad_providers.update(options.get("rejected_providers") or {})
    _collect(state)
    history_max = _history_max(options)
    for model_id in sorted(state.candidates):
        _compile_model(state, model_id, history_max)
    fleet = _fleet(state)
    result = options.get("result_factory", records.CompileResult)
    return result(
        fleet=fleet,
        sidecar=_sidecar(state, fleet),
        rejected=state.rejected,
        warnings=tuple(state.warnings),
        rejected_providers=state.bad_providers,
    )

#!/usr/bin/env python3
"""Deterministic generator and verifier for fleet.json with Codex v2 routes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import fleet_compiler as fc  # noqa: E402
from core import route_catalog_contract as rcc  # noqa: E402
from core.backend_adapter import FleetViolation, build_catalog  # noqa: E402
from core.catalog_routes import parse_routes, routes_catalog_hash  # noqa: E402

_O_NOFOLLOW: int = getattr(os, "O_NOFOLLOW", 0)
_SAFE_VER = re.compile(r"[^A-Za-z0-9._+-]+")


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Deterministic fleet generation output with verified contract hash."""

    fleet: dict[str, Any]
    fleet_bytes: bytes
    fleet_sha256: str
    catalog_hash: str
    contract: rcc.RouteCatalogContract
    updated_models: tuple[str, ...]


def _read_regular_bytes(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | _O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"not_regular_file: {path}")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            return handle.read()
    finally:
        if fd >= 0:
            os.close(fd)


def _contract_ver(base_url: object) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        return "unverified"
    tail = base_url.rstrip("/").rsplit("/", 1)[-1]
    return _SAFE_VER.sub("-", tail).strip("-") or "unverified"


def _model_cap(model: Mapping[str, Any]) -> rcc.ModelCapability:
    ctx, max_tok = model.get("context_window"), model.get("max_tokens")
    return rcc.ModelCapability(
        str(model["id"]),
        tuple(str(e) for e in model.get("efforts", ())),
        str(model.get("default_effort", "high")),
        int(ctx) if ctx else None,
        None,
        int(max_tok) if max_tok else None,
    )


def _collect_passthrough_caps(
    backends: Mapping[str, Any],
    models: Sequence[Any],
    codex_models: frozenset[str],
) -> dict[str, list[rcc.ModelCapability]]:
    caps: dict[str, list[rcc.ModelCapability]] = {}
    for model in models:
        if not isinstance(model, Mapping) or model.get("id") not in codex_models:
            continue
        routing = model.get("routing")
        routes = routing.get("routes", ()) if isinstance(routing, Mapping) else ()
        for route in routes:
            bid = str(route.get("backend", "")) if isinstance(route, Mapping) else ""
            bcfg = backends.get(bid)
            if (
                isinstance(bcfg, Mapping)
                and bcfg.get("kind") == rcc.BACKEND_KIND_PASSTHROUGH
            ):
                caps.setdefault(bid, []).append(_model_cap(model))
    return caps


def _passthrough_entries(
    fleet: Mapping[str, Any], codex_models: frozenset[str]
) -> tuple[rcc.VersionedRouteEntry, ...]:
    backends, models = fleet.get("backends"), fleet.get("models")
    if not isinstance(backends, Mapping) or not isinstance(models, list):
        return ()
    caps = _collect_passthrough_caps(backends, models, codex_models)
    out: list[rcc.VersionedRouteEntry] = []
    for bid in sorted(caps):
        ver = _contract_ver(backends[bid].get("base_url"))
        out.append(
            rcc.VersionedRouteEntry(
                bid, bid, rcc.BACKEND_KIND_PASSTHROUGH, f"openai.chat-completions.http.v1@{ver}",
                bool(backends[bid].get("enabled", True)), tuple(caps[bid]), False,
            )
        )
    return tuple(out)


def _build_codex_contract(fleet: Mapping[str, Any]) -> rcc.RouteCatalogContract:
    backends = fleet.get("backends")
    cfg = (
        backends.get(rcc.CODEX_LEGACY_ROUTE_ID)
        if isinstance(backends, Mapping)
        else None
    )
    if not isinstance(cfg, Mapping):
        raise rcc.RouteCatalogContractError("codex_backend_missing")
    if cfg.get("kind") != rcc.BACKEND_KIND_STDIO_RESIDENT:
        raise rcc.RouteCatalogContractError("codex_backend_not_resident")
    primary = rcc.build_codex_v2_primary_route(enabled=bool(cfg.get("enabled", True)))
    codex_ids = frozenset(cap.model_id for cap in primary.capabilities)
    entries = (
        primary,
        rcc.build_codex_passthrough_route(enabled=False),
        *_passthrough_entries(fleet, codex_ids),
    )
    contract = rcc.RouteCatalogContract(entries)
    resident, passthrough = rcc.separate_routes_by_transport(contract.entries)
    if not resident or not passthrough:
        raise rcc.RouteCatalogContractError("transport_separation_incomplete")
    if keys := rcc.find_forbidden_secret_keys(contract.canonical_dict()):
        raise rcc.RouteCatalogContractError("secret_field_forbidden", ",".join(keys))
    if not rcc.verify_catalog_hash(contract.entries, contract.catalog_hash):
        raise rcc.RouteCatalogContractError("catalog_hash_verification_failed")
    return contract


def _sync_model_entry(model: dict[str, Any], primary: rcc.VersionedRouteEntry) -> bool:
    cap = primary.capability_for(str(model.get("id", "")))
    if cap is None:
        return False
    model["efforts"] = list(cap.efforts)
    model["default_effort"] = cap.default_effort
    routing = model.get("routing")
    if not isinstance(routing, dict):
        return True
    raw_routes = routing.get("routes")
    if not isinstance(raw_routes, list):
        raise rcc.RouteCatalogContractError("routing_routes_invalid")
    rewritten = [
        {**r, "route_id": rcc.CODEX_V2_ROUTE_ID}
        if isinstance(r, Mapping) and r.get("backend") == rcc.CODEX_LEGACY_ROUTE_ID
        else r
        for r in raw_routes
    ]
    normalized = parse_routes(rewritten)
    routing["routes"] = normalized
    routing["catalog_hash"] = routes_catalog_hash(normalized)
    return True


def generate_fleet(
    providers_path: Path | None = None,
    fleet_meta_path: Path | None = None,
) -> SyncResult:
    """Compile providers.d deterministically into fleet.json bytes with Codex v2 routes."""
    kinds = fc.default_kinds()
    compiled = fc.compile_from_disk(providers_path, fleet_meta_path, kinds=kinds)
    fleet: dict[str, Any] = copy.deepcopy(compiled.fleet)
    if isinstance(aliases := fleet.get("aliases"), Mapping):
        rcc.validate_no_forbidden_aliases(aliases)
    contract = _build_codex_contract(fleet)
    primary = contract.route_for_id(rcc.CODEX_V2_ROUTE_ID)
    if primary is None:
        raise rcc.RouteCatalogContractError("codex_v2_route_missing")
    updated = [
        str(m["id"])
        for m in fleet.get("models", ())
        if isinstance(m, dict) and _sync_model_entry(m, primary)
    ]
    if sorted(updated) != sorted(c.model_id for c in primary.capabilities):
        raise rcc.RouteCatalogContractError("codex_models_incomplete")
    build_catalog(fleet, kinds, mode="strict", constraints_enabled=False)
    fleet_bytes = fc.render_fleet_json(fleet)
    return SyncResult(
        fleet, fleet_bytes, hashlib.sha256(fleet_bytes).hexdigest(),
        contract.catalog_hash, contract, tuple(sorted(updated)),
    )


def check_fleet_file(fleet_path: Path, expected: SyncResult) -> tuple[bool, str]:
    """Compare existing fleet.json against deterministic expected bytes."""
    try:
        actual = _read_regular_bytes(fleet_path)
    except OSError as exc:
        return False, f"fleet_unreadable: {exc}"
    if actual != expected.fleet_bytes:
        return False, f"fleet_bytes_mismatch: {fleet_path}"
    return True, "ok"


def _env_path(flag: Path | None, env_var: str, fallback: Path) -> Path:
    if flag is not None:
        return flag
    raw = os.environ.get(env_var, "").strip()
    return Path(os.path.expanduser(raw)) if raw else fallback


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    providers = _env_path(
        args.providers_dir, "BRIDGE_PROVIDERS_DIR", ROOT / "providers.d"
    )
    fleet_meta = args.fleet_meta or (providers / "_fleet.yaml")
    fleet_path = _env_path(args.fleet, "BRIDGE_FLEET_PATH", ROOT / "fleet.json")
    return providers, fleet_meta, fleet_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Codex v2 routes in fleet.json.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify fleet.json bytes")
    mode.add_argument("--write", action="store_true", help="write fleet.json")
    parser.add_argument("--providers-dir", type=Path, default=None)
    parser.add_argument("--fleet-meta", type=Path, default=None)
    parser.add_argument("--fleet", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="emit JSON status")
    return parser


def _emit(payload: Mapping[str, Any], *, as_json: bool, ok: bool) -> None:
    stream = sys.stdout if ok else sys.stderr
    if as_json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False), file=stream)
        return
    tag = "OK" if ok else "FAIL"
    print(
        f"{tag}: mode={payload['mode']} detail={payload['detail']} "
        f"catalog_hash={payload['catalog_hash']} fleet_sha256={payload['fleet_sha256']}",
        file=stream,
    )


_SYNC_ERRORS = (
    fc.CompileError,
    FleetViolation,
    rcc.RouteCatalogContractError,
    ValueError,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    providers, fleet_meta, fleet_path = _resolve_paths(args)
    mode = "write" if args.write else "check"
    try:
        result = generate_fleet(providers, fleet_meta)
    except _SYNC_ERRORS as exc:
        err = {
            "ok": False,
            "mode": mode,
            "detail": str(exc),
            "catalog_hash": "",
            "fleet_sha256": "",
        }
        _emit(err, as_json=args.json, ok=False)
        return 1
    if args.write:
        fc.atomic_write_bytes(fleet_path, result.fleet_bytes)
        ok, detail = True, f"wrote:{fleet_path}"
    else:
        ok, detail = check_fleet_file(fleet_path, result)
    payload = {
        "ok": ok,
        "mode": mode,
        "detail": detail,
        "catalog_hash": result.catalog_hash,
        "fleet_sha256": result.fleet_sha256,
        "updated_models": list(result.updated_models),
        "resident_v2_routes": [r.route_id for r in result.contract.resident_v2_routes],
    }
    _emit(payload, as_json=args.json, ok=ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

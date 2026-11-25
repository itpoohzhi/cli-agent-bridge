"""Pure versioned route catalog DTOs and canonical catalog_hash contract (Zero-I/O)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import NoReturn, TypeAlias, cast

CONTRACT_SCHEMA_VERSION = 1
CODEX_V2_ROUTE_ID, CODEX_LEGACY_ROUTE_ID, CODEX_PASSTHROUGH_ROUTE_ID = "codex-app-server-v2", "codex", "codex-passthrough"
BACKEND_KIND_STDIO_RESIDENT, BACKEND_KIND_PASSTHROUGH = "stdio_resident", "passthrough"
ALLOWED_BACKEND_KINDS = frozenset({BACKEND_KIND_STDIO_RESIDENT, BACKEND_KIND_PASSTHROUGH})
CODEX_APP_SERVER_V2_CONTRACT, CODEX_APP_SERVER_V2_PREFIX = "codex.app-server.v2@codex-cli-0.171.0-alpha.13", "codex.app-server.v2@"
TRANSPORT_FAMILY_RESIDENT_V2, TRANSPORT_FAMILY_RESIDENT_LEGACY, TRANSPORT_FAMILY_PASSTHROUGH_HTTP = "resident_v2", "resident_legacy", "passthrough_http"
SOL_MODEL_ID, SOL62_MODEL_ID, TERRA_MODEL_ID = "gpt-6.1-sol", "gpt-6.2-sol", "gpt-6.1-terra"
FORBIDDEN_ALIAS_MODEL_IDS, UNAVAILABLE_MODEL_IDS = frozenset({SOL62_MODEL_ID}), frozenset()
SOL_EFFORTS, TERRA_EFFORTS = ("low", "medium", "high", "xhigh", "max"), ("low", "medium", "high")

_CONTRACT_PREFIXES = (
    (CODEX_APP_SERVER_V2_PREFIX, TRANSPORT_FAMILY_RESIDENT_V2),
    ("codex.app-server.legacy@", TRANSPORT_FAMILY_RESIDENT_LEGACY),
    ("codex.app-server.v1@", TRANSPORT_FAMILY_RESIDENT_LEGACY),
    ("codex.passthrough.http.v1@", TRANSPORT_FAMILY_PASSTHROUGH_HTTP),
    ("openai.chat-completions.http.v1@", TRANSPORT_FAMILY_PASSTHROUGH_HTTP),
)
_RANK = {"off": 0, "low": 1, "medium": 2, "high": 3, "xhigh": 4, "max": 5}
_ID_RE, _VER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"), re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_SEC_VAL = re.compile(r"(?i)(^sk-[a-z0-9_-]{4,}|bearer\s+\S+|eyJ[A-Za-z0-9_-]{8,}\.)")
_SEC_KEYS = frozenset("api_key apikey secret token authorization bearer password credential credentials auth".split())


class RouteCatalogContractError(ValueError):
    """Fail-closed validation error for versioned route catalog contracts."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise RouteCatalogContractError(code, detail)


def _req_id(val: object, field: str) -> str:
    if not isinstance(val, str) or _ID_RE.fullmatch(val) is None:
        _fail(f"invalid_{field}", repr(val))
    if _SEC_VAL.search(val) is not None:
        _fail("secret_in_identifier", field)
    return val


def _req_bool(val: object, field: str) -> bool:
    return val if type(val) is bool else _fail(f"invalid_{field}", str(val))


def _pos_int(val: object, field: str) -> int | None:
    if val is None:
        return None
    return val if type(val) is int and val > 0 else _fail(f"invalid_{field}", str(val))


def _norm_efforts(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        _fail("invalid_efforts", "sequence_required")
    items = tuple(_req_id(item, "effort") for item in raw)
    if not items or len(set(items)) != len(items):
        _fail("invalid_efforts", "empty_or_duplicate")
    return tuple(sorted(items, key=lambda n: (_RANK.get(n, 99), n)))


def find_forbidden_secret_keys(raw: Mapping[str, object]) -> tuple[str, ...]:
    """Finds secret-bearing keys anywhere inside a raw catalog mapping."""
    found: list[str] = []
    stack: list[tuple[str, object]] = [("", raw)]
    while stack:
        prefix, node = stack.pop()
        if isinstance(node, Mapping):
            for k, v in cast(Mapping[object, object], node).items():
                low, path = str(k).lower(), f"{prefix}.{k}" if prefix else str(k)
                if low in _SEC_KEYS or (set(re.split(r"[^a-z0-9]+", low)) & _SEC_KEYS):
                    found.append(path)
                stack.append((path, v))
        elif isinstance(node, (list, tuple)):
            stack.extend((f"{prefix}[{i}]", x) for i, x in enumerate(node))
    return tuple(sorted(found))


def classify_upstream_contract(upstream_contract: str) -> str:
    """Validates versioned upstream_contract and returns its transport family."""
    if upstream_contract.count("@") != 1:
        _fail("invalid_upstream_contract", upstream_contract)
    if _SEC_VAL.search(upstream_contract) is not None:
        _fail("secret_in_upstream_contract")
    _, ver = upstream_contract.split("@", 1)
    if _VER_RE.fullmatch(ver) is None:
        _fail("invalid_contract_version", ver)
    for prefix, family in _CONTRACT_PREFIXES:
        if upstream_contract.startswith(prefix):
            return family
    _fail("unknown_upstream_contract", upstream_contract)


def validate_route_contract_separation(route_id: str, backend_kind: str, upstream_contract: str) -> str:
    """Enforces strict separation between resident v2 and passthrough contracts."""
    if backend_kind not in ALLOWED_BACKEND_KINDS:
        _fail("invalid_backend_kind", repr(backend_kind))
    fam = classify_upstream_contract(upstream_contract)
    is_http = fam == TRANSPORT_FAMILY_PASSTHROUGH_HTTP
    if (backend_kind == BACKEND_KIND_PASSTHROUGH) != is_http:
        _fail("contract_backend_kind_mismatch", backend_kind)
    if route_id == CODEX_V2_ROUTE_ID and fam != TRANSPORT_FAMILY_RESIDENT_V2:
        _fail("resident_v2_route_contract_mismatch", fam)
    if route_id == CODEX_PASSTHROUGH_ROUTE_ID and not is_http:
        _fail("passthrough_route_contract_mismatch", fam)
    return fam


@dataclass(frozen=True, slots=True)
class ModelCapability:
    model_id: str
    efforts: tuple[str, ...]
    default_effort: str
    context_window: int | None = None
    safe_input_tokens: int | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        _ = _req_id(self.model_id, "model_id")
        eff = _norm_efforts(self.efforts)
        object.__setattr__(self, "efforts", eff)
        if _req_id(self.default_effort, "default_effort") not in eff:
            _fail("default_effort_not_in_efforts", self.default_effort)
        ctx, safe = _pos_int(self.context_window, "context_window"), _pos_int(self.safe_input_tokens, "safe_input_tokens")
        _ = _pos_int(self.max_tokens, "max_tokens")
        if ctx is not None and safe is not None and safe > ctx:
            _fail("safe_input_exceeds_context", f"{safe}>{ctx}")

    def canonical_dict(self) -> dict[str, object]:
        base: dict[str, object] = {"model_id": self.model_id, "efforts": list(self.efforts), "default_effort": self.default_effort}
        opts = {"context_window": self.context_window, "safe_input_tokens": self.safe_input_tokens, "max_tokens": self.max_tokens}
        return {**base, **{k: v for k, v in opts.items() if v is not None}}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ModelCapability:
        if not isinstance(cast(object, raw), Mapping):
            _fail("invalid_capability_mapping")
        return cls(
            _req_id(raw.get("model_id", ""), "model_id"), _norm_efforts(raw.get("efforts", ())),
            _req_id(raw.get("default_effort", ""), "default_effort"), _pos_int(raw.get("context_window"), "context_window"),
            _pos_int(raw.get("safe_input_tokens"), "safe_input_tokens"), _pos_int(raw.get("max_tokens"), "max_tokens"),
        )


def _parse_caps(raw: object) -> tuple[ModelCapability, ...]:
    if raw is None:
        return ()
    if isinstance(raw, Mapping):
        out: list[ModelCapability] = []
        for mid, cfg in cast(Mapping[object, object], raw).items():
            if isinstance(cfg, ModelCapability):
                out.append(cfg)
            elif isinstance(cfg, Mapping):
                out.append(ModelCapability.from_mapping({"model_id": str(mid), **cfg}))
            else:
                _fail("invalid_capability_entry", str(mid))
        return tuple(out)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        return tuple(x if isinstance(x, ModelCapability) else ModelCapability.from_mapping(x) for x in raw)  # type: ignore[arg-type]
    _fail("invalid_capabilities_container")


@dataclass(frozen=True, slots=True)
class VersionedRouteEntry:
    route_id: str
    backend: str
    backend_kind: str
    upstream_contract: str
    enabled: bool = True
    capabilities: tuple[ModelCapability, ...] = ()
    zero_canon_attested: bool = False
    schema_version: int = CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            _fail("invalid_schema_version")
        _ = _req_id(self.route_id, "route_id"), _req_id(self.backend, "backend")
        _ = validate_route_contract_separation(self.route_id, self.backend_kind, self.upstream_contract)
        _ = _req_bool(self.enabled, "enabled"), _req_bool(self.zero_canon_attested, "zero_canon_attested")
        if self.zero_canon_attested and self.backend_kind == BACKEND_KIND_PASSTHROUGH:
            _fail("passthrough_cannot_attest_zero_canon")
        caps = _parse_caps(self.capabilities)
        if len({c.model_id for c in caps}) != len(caps):
            _fail("duplicate_model_capability", self.route_id)
        object.__setattr__(self, "capabilities", tuple(sorted(caps, key=lambda c: c.model_id)))

    @property
    def transport_family(self) -> str: return classify_upstream_contract(self.upstream_contract)
    @property
    def is_resident_v2(self) -> bool: return self.transport_family == TRANSPORT_FAMILY_RESIDENT_V2
    @property
    def is_passthrough(self) -> bool: return self.transport_family == TRANSPORT_FAMILY_PASSTHROUGH_HTTP
    def capability_for(self, model_id: str) -> ModelCapability | None: return next((c for c in self.capabilities if c.model_id == model_id), None)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "route_id": self.route_id, "backend": self.backend,
            "backend_kind": self.backend_kind, "upstream_contract": self.upstream_contract, "enabled": self.enabled,
            "zero_canon_attested": self.zero_canon_attested, "capabilities": [c.canonical_dict() for c in self.capabilities],
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object], *, reject_secrets: bool = False) -> VersionedRouteEntry:
        if not isinstance(cast(object, raw), Mapping):
            _fail("invalid_route_mapping")
        if reject_secrets and (keys := find_forbidden_secret_keys(raw)):
            _fail("secret_field_forbidden", ",".join(keys))
        kind, contract, ver = raw.get("backend_kind", raw.get("kind", "")), raw.get("upstream_contract", ""), raw.get("schema_version", CONTRACT_SCHEMA_VERSION)
        if type(ver) is not int or ver != CONTRACT_SCHEMA_VERSION:
            _fail("invalid_schema_version", str(ver))
        return cls(
            _req_id(raw.get("route_id", ""), "route_id"), _req_id(raw.get("backend", ""), "backend"),
            kind if isinstance(kind, str) else "", contract if isinstance(contract, str) else "",
            _req_bool(raw.get("enabled", True), "enabled"), _parse_caps(raw.get("capabilities")),
            _req_bool(raw.get("zero_canon_attested", False), "zero_canon_attested"), ver,
        )


RouteInput: TypeAlias = VersionedRouteEntry | Mapping[str, object]


def _coerce(item: RouteInput) -> VersionedRouteEntry:
    if isinstance(item, VersionedRouteEntry):
        return item
    return VersionedRouteEntry.from_mapping(item) if isinstance(cast(object, item), Mapping) else _fail("invalid_route_entry")


@dataclass(frozen=True, slots=True)
class RouteCatalogContract:
    entries: tuple[VersionedRouteEntry, ...]
    schema_version: int = CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            _fail("invalid_schema_version")
        coerced = tuple(_coerce(item) for item in self.entries)
        if len({e.route_id for e in coerced}) != len(coerced):
            _fail("duplicate_route_id")
        object.__setattr__(self, "entries", tuple(sorted(coerced, key=lambda e: (e.route_id, e.backend, e.upstream_contract))))

    @property
    def catalog_hash(self) -> str: return compute_catalog_hash(self.entries)
    @property
    def resident_v2_routes(self) -> tuple[VersionedRouteEntry, ...]: return tuple(e for e in self.entries if e.is_resident_v2)
    @property
    def passthrough_routes(self) -> tuple[VersionedRouteEntry, ...]: return tuple(e for e in self.entries if e.is_passthrough)
    def route_for_id(self, route_id: str) -> VersionedRouteEntry | None: return next((e for e in self.entries if e.route_id == route_id), None)
    def canonical_dict(self) -> dict[str, object]: return {"schema_version": self.schema_version, "routes": [e.canonical_dict() for e in self.entries]}


def canonical_catalog_bytes(entries: Iterable[RouteInput]) -> bytes:
    """Encodes static versioned route entries into canonical UTF-8 JSON bytes."""
    doc = RouteCatalogContract(tuple(_coerce(e) for e in entries)).canonical_dict()
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def compute_catalog_hash(entries: Iterable[RouteInput]) -> str:
    return hashlib.sha256(canonical_catalog_bytes(entries)).hexdigest()


def verify_catalog_hash(entries: Iterable[RouteInput], expected_hash: str) -> bool:
    return bool(expected_hash) and compute_catalog_hash(entries) == expected_hash


def separate_routes_by_transport(entries: Iterable[RouteInput]) -> tuple[tuple[VersionedRouteEntry, ...], tuple[VersionedRouteEntry, ...]]:
    cat = RouteCatalogContract(tuple(_coerce(e) for e in entries))
    return tuple(e for e in cat.entries if e.backend_kind == BACKEND_KIND_STDIO_RESIDENT), tuple(e for e in cat.entries if e.backend_kind == BACKEND_KIND_PASSTHROUGH)


def validate_no_forbidden_aliases(aliases: Mapping[str, Mapping[str, object]]) -> None:
    forbidden = FORBIDDEN_ALIAS_MODEL_IDS | UNAVAILABLE_MODEL_IDS
    for name, target in aliases.items():
        bid = str(target.get("backend_id", ""))
        if name in forbidden or bid in forbidden:
            _fail("forbidden_model_alias", f"{name}->{bid}")


def build_codex_v2_primary_route(*, enabled: bool = True) -> VersionedRouteEntry:
    sol = ModelCapability(SOL_MODEL_ID, SOL_EFFORTS, "high", 272_000, 200_000, 128_000)
    sol62 = ModelCapability(SOL62_MODEL_ID, SOL_EFFORTS, "high", 272_000, 200_000, 128_000)
    terra = ModelCapability(TERRA_MODEL_ID, TERRA_EFFORTS, "high", 500_000, 340_000, 128_000)
    return VersionedRouteEntry(CODEX_V2_ROUTE_ID, CODEX_LEGACY_ROUTE_ID, BACKEND_KIND_STDIO_RESIDENT, CODEX_APP_SERVER_V2_CONTRACT, enabled, (sol, sol62, terra), True)


def build_codex_passthrough_route(*, contract_version: str = "unverified", enabled: bool = False) -> VersionedRouteEntry:
    return VersionedRouteEntry(CODEX_PASSTHROUGH_ROUTE_ID, CODEX_PASSTHROUGH_ROUTE_ID, BACKEND_KIND_PASSTHROUGH, f"codex.passthrough.http.v1@{contract_version}", enabled)

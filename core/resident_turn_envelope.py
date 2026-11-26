from __future__ import annotations

import dataclasses
import hashlib
import hmac
import uuid
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast

from core.backend_routing_models import ImageAttachment, Transcript
from core.resident_canonical import (
    DEFAULT_SAFE_FWD_ENV_KEYS as DEFAULT_SAFE_FWD_ENV_KEYS,
    _canon_key as _canon_key,
    _canonical as _canonical,
    _fail_if,
    assert_emulate_tools_bool as assert_emulate_tools_bool,
    compute_tool_contract_fingerprint as compute_tool_contract_fingerprint,
    deep_freeze as deep_freeze,
    normalize_child_env as normalize_child_env,
    strip_bridge_secrets as strip_bridge_secrets,
    thaw_frozen_value as thaw_frozen_value,
    validate_canonical_depth as validate_canonical_depth,
)
from core.resident_identity import ResidentIdentity, ResidentRequestError, validate_hmac_secret
from core.stdio_resident.types import SlotAffinityKey
from core.zero_canon_fs import read_gigarc_bool, resolve_hub_dynamic_config

WARM_DELTA_INTEGRITY_FLAG: Final[str] = "BRIDGE_CODEX_WARM_DELTA_INTEGRITY_ENABLED"


def is_warm_delta_integrity_enabled(
    environ: Mapping[str, str] | None = None, config_path: Path | None = None
) -> bool:
    """Kill-switch целостности warm delta (`dynamic_config.json > env > False`)."""
    path = config_path if config_path is not None else resolve_hub_dynamic_config(environ)
    return read_gigarc_bool(WARM_DELTA_INTEGRITY_FLAG, path, environ=environ, default=False)


def _system_digest(rpc: Transcript | None, supplied: str) -> str:
    res = supplied
    if not res:
        items = rpc.items if rpc else ()
        texts = [item.text for item in items if not bool({item.role} - {"system"})]
        lead = getattr(rpc, "system", None)
        if lead and is_warm_delta_integrity_enabled():
            texts = [lead, *texts]
        res = hashlib.sha256("\n\n".join(texts).encode("utf-8")).hexdigest()
    return res


def _translate_depth_error(exc: ValueError) -> None:
    _fail_if(exc.args[:1] == ("nesting_too_deep",), ResidentRequestError(400, "invalid_request"))
    raise exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidentTurnEnvelope:
    identity: ResidentIdentity
    backend_id: str
    model: str
    effort: str
    cwd_norm: str
    secret: InitVar[bytes]
    review_profile: str = "standard"
    rpc: Transcript | None = field(default_factory=Transcript)
    full_prompt: str = ""
    emulate_tools: bool = False
    tool_choice: object = None
    tool_schemas: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    images: tuple[ImageAttachment, ...] = ()
    fwd_env: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}), repr=False)
    system_digest: str = ""
    tool_contract_fingerprint: str = ""
    env_digest: str = ""

    def __post_init__(self, secret: bytes) -> None:
        text_values = (
            self.backend_id,
            self.model,
            self.effort,
            self.cwd_norm,
            self.review_profile,
            self.full_prompt,
            self.system_digest,
        )
        _fail_if(not all(isinstance(value, str) for value in text_values), TypeError("resident envelope text fields must be str"))
        validate_hmac_secret(secret)
        try:
            fingerprint = compute_tool_contract_fingerprint(
                self.emulate_tools,
                self.tool_schemas,
                self.tool_choice,
            )
            schemas = cast(Mapping[str, Any], deep_freeze(self.tool_schemas))
            choice = deep_freeze(self.tool_choice)
            images = cast(tuple[ImageAttachment, ...], deep_freeze(self.images))
        except ValueError as exc:
            _translate_depth_error(exc)
            raise AssertionError("unreachable") from exc
        frozen_env = MappingProxyType(dict(self.fwd_env))
        env_payload = _canon_key(sorted(frozen_env.items())).encode("ascii")
        object.__setattr__(self, "tool_schemas", schemas)
        object.__setattr__(self, "tool_choice", choice)
        object.__setattr__(self, "images", images)
        object.__setattr__(self, "fwd_env", frozen_env)
        object.__setattr__(self, "system_digest", _system_digest(self.rpc, self.system_digest))
        object.__setattr__(self, "tool_contract_fingerprint", fingerprint)
        object.__setattr__(self, "env_digest", hmac.new(secret, env_payload, hashlib.sha256).hexdigest()[:32])

    def __repr__(self) -> str:
        values = ", ".join(
            f"{item.name}={getattr(self, item.name)!r}"
            for item in dataclasses.fields(self)
            if item.repr
        )
        return f"ResidentTurnEnvelope({values})"

    def with_ephemeral_identity(self, reason: str = "admission_cap") -> ResidentTurnEnvelope:
        new_identity = dataclasses.replace(
            self.identity,
            ephemeral=True,
            cache_key="",
            scoped_session_id=uuid.uuid4().hex,
            degradation_reason=reason,
        )
        clone = object.__new__(type(self))
        for item in dataclasses.fields(self):
            value = new_identity if all((item.repr, not bool({item.name} - {"identity"}))) else getattr(self, item.name)
            object.__setattr__(clone, item.name, value)
        return cast(ResidentTurnEnvelope, clone)

    def affinity_key(self) -> SlotAffinityKey:
        return SlotAffinityKey(
            owner_hash=self.identity.principal_hash,
            chat_key=self.identity.scoped_session_id,
            backend_id=self.backend_id,
            model=self.model,
            effort=self.effort,
            cwd_norm=self.cwd_norm,
            review_profile=self.review_profile,
            env_digest=self.env_digest,
        )

from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from core.backend_adapter import StreamSink, TurnContext
from core.backend_routing_models import ImageAttachment, Transcript
from core.resident_canonical import (
    DEFAULT_SAFE_FWD_ENV_KEYS,
    _fail_if,
    assert_emulate_tools_bool,
    compute_tool_contract_fingerprint,
    normalize_child_env,
    thaw_frozen_value,
    validate_canonical_depth,
)
from core.resident_identity import (
    IdentityInputs,
    ResidentIdentity,
    ResidentRequestError,
    resolve_resident_identity,
    validate_hmac_secret,
)
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.stdio_resident.runtime_types import ResourceLimitError
from core.subbridge_zero_canon import normalize_review_profile

VENDOR_DENIED_ENV_PREFIXES = (
    "DROID_", "FACTORY_", "AWS_", "AZURE_", "CLOUDSDK_", "GRPC_",
    "GEMINI_", "ANTIGRAVITY_", "AGY_", "CLAUDE_", "CODEX_", "OPENAI_",
    "ANTHROPIC_", "GOOGLE_", "VERTEX_", "HF_", "GH_",
)
DEFAULT_HEARTBEAT_S = 15.0
_ADAPTER_OPTION_KEYS = frozenset({
    "protocol", "cli_argv", "argv", "cli_args", "sandbox_flags",
    "output_format", "output_format_flag", "output_format_args", "step_dedup",
})
_AUTH_VALUES = {
    "1": True, "true": True, "yes": True, "on": True,
    "0": False, "false": False, "no": False, "off": False,
}
_CONTENT_KINDS = frozenset({"content", "reasoning_content"})


@dataclass(frozen=True, slots=True)
class ResidentTrustConfig:
    trusted_owner_hash: Any = None
    trusted_identity: ResidentIdentity | None = None
    require_auth: bool = False
    protocol: str = ""
    allowed_env_keys: frozenset[str] = DEFAULT_SAFE_FWD_ENV_KEYS
    extra_denied_prefixes: tuple[str, ...] = VENDOR_DENIED_ENV_PREFIXES


def _pick(val: Any, default: Any) -> Any:
    res = val if val else default
    return res


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    res = cast(Mapping[str, Any], value) if isinstance(value, Mapping) else None
    return res


def parse_require_auth_env(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if isinstance(environ, type(None)) else environ
    raw = source.get("BRIDGE_STDIO_RESIDENT_REQUIRE_AUTH", "false")
    return _AUTH_VALUES.get(raw.strip().lower(), False)


def extract_adapter_options(config: Mapping[str, Any]) -> dict[str, Any]:
    transport = _as_mapping(config.get("transport"))
    tr_bridge = _as_mapping(transport.get("bridge")) if transport else None
    bridge = _as_mapping(config.get("bridge"))
    opts = next(
        (_as_mapping(c.get("options")) for c in (tr_bridge, bridge, config) if all((bool(c), bool(_as_mapping(c.get("options")) if c else None)))),
        None,
    )
    out = dict(opts) if opts else {k: v for k, v in config.items() if bool({k} & _ADAPTER_OPTION_KEYS)}
    return out


def resolve_raw_argv(
    cli_argv: list[str] | tuple[str, ...] | str | None,
    options: Mapping[str, Any],
    config: Mapping[str, Any],
) -> object:
    result: object = cli_argv
    if isinstance(result, type(None)):
        transport = _as_mapping(config.get("transport"))
        tr_bridge = _as_mapping(transport.get("bridge")) if transport else None
        bridge = _as_mapping(config.get("bridge"))
        sources = ((options, ("cli_argv", "argv")), (config, ("cli_argv", "wrapper")), (tr_bridge, ("cli_argv", "wrapper")), (bridge, ("cli_argv", "wrapper")))
        vals = (src[key] for src, keys in sources if src for key in keys if not isinstance(src.get(key), type(None)))
        result = next(vals, None)
    return result


def request_mapping(request: dict[str, Any] | Any) -> Mapping[str, Any]:
    raw = request if isinstance(request, Mapping) else getattr(request, "__dict__", None)
    out = cast(Mapping[str, Any], raw) if isinstance(raw, Mapping) else {}
    return out


def _prompt(data: Mapping[str, Any]) -> str:
    prompt = data.get("prompt")
    out = prompt if isinstance(prompt, str) else ""
    if not isinstance(prompt, str):
        messages = data.get("messages")
        items = reversed(cast(list[object], messages)) if isinstance(messages, list) else ()
        contents = (m.get("content") for item in items if (m := _as_mapping(item)))
        out = next((cast(str, c) for c in contents if isinstance(c, str)), "")
    return out


def _text(value: object, fallback: str) -> str:
    candidate = fallback if isinstance(value, type(None)) else value
    _fail_if(not isinstance(candidate, str), ResidentRequestError(400, "invalid_request"))
    return cast(str, candidate)


def _validated_tools_and_env(
    data: Mapping[str, Any],
    trust: ResidentTrustConfig,
) -> tuple[bool, Mapping[str, Any], Any, tuple[ImageAttachment, ...], Mapping[str, str]]:
    emulate_tools = data.get("emulate_tools", False)
    tool_schemas = data.get("tool_schemas")
    raw_images = data.get("images")
    tool_choice = data.get("tool_choice")
    try:
        emulate = assert_emulate_tools_bool(emulate_tools)
        _fail_if(not isinstance(tool_schemas, (type(None), Mapping)), TypeError("tool_schemas"))
        _fail_if(not isinstance(raw_images, (type(None), list, tuple)), TypeError("images"))
        child_env = normalize_child_env(data.get("env"), allowed_keys=trust.allowed_env_keys, extra_denied_prefixes=trust.extra_denied_prefixes)
        _ = compute_tool_contract_fingerprint(emulate, tool_schemas, tool_choice)
        validate_canonical_depth(raw_images, max_depth=63)
        validate_canonical_depth(tool_choice, max_depth=63)
    except (TypeError, ValueError) as exc:
        raise ResidentRequestError(400, "invalid_request") from exc
    schemas = cast(Mapping[str, Any], _pick(tool_schemas, {}))
    images = tuple(img if isinstance(img, ImageAttachment) else ImageAttachment(**cast(Mapping[str, Any], img)) for img in _pick(raw_images, ()))
    return emulate, schemas, tool_choice, images, child_env


def _resolve_identity_for_chat(data: Mapping[str, Any], secret: bytes, trust: ResidentTrustConfig) -> ResidentIdentity:
    res: ResidentIdentity | None = trust.trusted_identity
    if not res:
        headers = _as_mapping(data.get("_headers"))
        res = resolve_resident_identity(
            IdentityInputs(
                request=data,
                headers=cast(Mapping[str, str] | None, headers),
                extra=data,
                secret=secret,
                trusted_principal_hash=trust.trusted_owner_hash,
                scope=data.get("scope", ""),
                subagent_id=data.get("subagent_id", ""),
                review_profile=normalize_review_profile(_text(data.get("review_profile"), "")),
                protocol=trust.protocol,
                require_auth=bool(trust.require_auth),
                force_ephemeral=bool(data.get("force_ephemeral", False)),
                turn_id=_text(data.get("turn_id"), ""),
            )
        )
    return res


def build_resident_envelope_from_chat(
    adapter_id: str,
    data: Mapping[str, Any],
    secret: bytes,
    trust_cfg: ResidentTrustConfig | None = None,
) -> tuple[ResidentTurnEnvelope, str]:
    validate_hmac_secret(secret)
    trust = _pick(trust_cfg, ResidentTrustConfig())
    raw_ctx = _pick(_as_mapping(data.get("turn_context")), {})
    cwd = _text(data.get("cwd"), os.getcwd())
    raw_rpc = data.get("rpc", raw_ctx.get("rpc"))
    rpc = raw_rpc if isinstance(raw_rpc, Transcript) else Transcript()
    raw_prompt = _prompt(data)
    emulate, schemas, choice, images, child_env = _validated_tools_and_env(data, trust)
    identity = _resolve_identity_for_chat(data, secret, trust)
    envelope = ResidentTurnEnvelope(
        identity=identity,
        backend_id=_text(adapter_id, ""),
        model=_text(data.get("model", raw_ctx.get("model")), "default"),
        effort=_text(data.get("effort", raw_ctx.get("effort")), "medium"),
        cwd_norm=os.path.realpath(os.path.abspath(os.path.expanduser(cwd))),
        secret=secret,
        review_profile=normalize_review_profile(_text(data.get("review_profile"), "")),
        rpc=rpc,
        full_prompt=raw_prompt,
        emulate_tools=emulate,
        tool_choice=choice,
        tool_schemas=schemas,
        images=images,
        fwd_env=child_env,
    )
    return envelope, raw_prompt


def build_turn_request_from_ctx(adapter_id: str, ctx: TurnContext, profile: str) -> dict[str, Any]:
    chat_id = next((v for v in (ctx.conversation_id, ctx.turn_id, ctx.rid) if v), "default")
    return {
        "chat_id": chat_id,
        "backend_id": adapter_id,
        "model": ctx.model,
        "effort": ctx.effort,
        "cwd": ctx.cwd if ctx.cwd else os.getcwd(),
        "prompt": ctx.prompt,
        "env": ctx.fwd_env,
        "rpc": ctx.rpc,
        "images": thaw_frozen_value(ctx.images),
        "tool_schemas": thaw_frozen_value(ctx.tool_schemas),
        "emulate_tools": ctx.emulate_tools,
        "tool_choice": thaw_frozen_value(getattr(ctx, "tool_choice", None)),
        "conversation_id": ctx.conversation_id,
        "force_ephemeral": ctx.conversation_ephemeral,
        "review_profile": profile,
        "turn_context": {"model": ctx.model, "effort": ctx.effort, "review_profile": profile, "rpc": ctx.rpc},
    }


def wrap_emulate_tools_sse_writer(
    sse_writer: StreamSink | None,
    emulate_tools: bool,
    max_bytes: int,
    close_stream: Callable[[], None],
    keepalive: Callable[[], bool] | None = None,
) -> StreamSink | None:
    result = sse_writer
    if all((emulate_tools, bool(sse_writer))):
        sink = cast(StreamSink, sse_writer)
        limit = max(1024, int(max_bytes if max_bytes else 4194304))
        accumulated = 0
        last_hb = time.monotonic()

        def write(kind: str, val: str) -> bool:
            nonlocal accumulated, last_hb
            out = True
            if not bool({kind} & _CONTENT_KINDS):
                out = sink(kind, val)
            else:
                accumulated += len(val.encode("utf-8"))
                if accumulated > limit:
                    close_stream()
                    raise ResourceLimitError("output_limit_exceeded")
                now = time.monotonic()
                if all((bool(keepalive), now - last_hb >= DEFAULT_HEARTBEAT_S)):
                    _ = cast(Callable[[], bool], keepalive)()
                    last_hb = now
            return out

        result = cast(StreamSink, write)
    return result

"""Wave W1: Anthropic `cache_control` для opencode-go-claude (claude-haiku-5-5)."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.anthropic_cache_control import (
    FLAG_ANTHROPIC_CACHE_CONTROL,
    STRATEGY_ANTHROPIC_EPHEMERAL,
    inject_anthropic_cache_control,
)
from core.backend_params import (
    BACKEND_PARAMS_INVALID,
    extract_backend_params,
    serialize_sidecar_params,
    validate_backend_params,
)
from adapters import ADAPTER_KINDS
from core.manifest_dialect_dispatch import apply_passthrough_transforms
from core.provider_manifest import ParamsConfig, load_manifests

LONG = "x" * 3000


def _count_breakpoints(node: Any) -> int:
    if isinstance(node, Mapping):
        return int("cache_control" in node) + sum(_count_breakpoints(v) for v in node.values())
    if isinstance(node, list):
        return sum(_count_breakpoints(item) for item in node)
    return 0


def _msg(role: str, content: Any) -> dict[str, Any]:
    return {"role": role, "content": content}


# ---- чистая функция inject_anthropic_cache_control -----------------------------------


def test_short_system_untouched() -> None:
    payload = {"messages": [_msg("system", "short"), _msg("user", "hi")]}
    assert inject_anthropic_cache_control(payload) == payload


def test_missing_or_empty_messages_untouched() -> None:
    assert inject_anthropic_cache_control({"model": "m"}) == {"model": "m"}
    assert inject_anthropic_cache_control({"messages": []}) == {"messages": []}
    assert inject_anthropic_cache_control({"messages": "oops"}) == {"messages": "oops"}


def test_long_system_string_becomes_text_block() -> None:
    out = inject_anthropic_cache_control({"messages": [_msg("system", LONG), _msg("user", "hi")]})
    block = out["messages"][0]["content"]
    assert block == [{"type": "text", "text": LONG, "cache_control": {"type": "ephemeral"}}]
    assert out["messages"][1] == _msg("user", "hi")


def test_long_system_blocks_annotates_last_text_keeps_image() -> None:
    image = {"type": "image_url", "image_url": {"url": "data:..."}}
    blocks = [{"type": "text", "text": LONG}, image, {"type": "text", "text": "tail"}]
    out = inject_anthropic_cache_control({"messages": [_msg("system", blocks)]})
    got = out["messages"][0]["content"]
    assert got[0] == {"type": "text", "text": LONG}
    assert got[1] == image
    assert got[2] == {"type": "text", "text": "tail", "cache_control": {"type": "ephemeral"}}


def test_developer_role_counts_as_system_prefix() -> None:
    out = inject_anthropic_cache_control({"messages": [_msg("developer", LONG)]})
    assert _count_breakpoints(out) == 1


def test_multi_turn_second_breakpoint_skips_tool_only_assistant() -> None:
    tool_only = {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]}
    messages = [_msg("system", LONG), _msg("user", LONG), tool_only, _msg("user", "next")]
    out = inject_anthropic_cache_control({"messages": messages})
    assert _count_breakpoints(out) == 2
    assert out["messages"][1]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in out["messages"][2]
    assert out["messages"][3] == _msg("user", "next")


def test_multi_turn_marks_penultimate_when_it_has_text() -> None:
    messages = [_msg("user", LONG), _msg("assistant", LONG), _msg("user", "q2")]
    out = inject_anthropic_cache_control({"messages": messages})
    assert out["messages"][1]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert _count_breakpoints(out) == 1


def test_two_messages_history_gets_no_second_breakpoint() -> None:
    out = inject_anthropic_cache_control({"messages": [_msg("user", LONG), _msg("assistant", LONG)]})
    assert _count_breakpoints(out) == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"messages": [_msg("system", [{"type": "text", "text": LONG, "cache_control": {"type": "ephemeral"}}])]},
        {"messages": [_msg("system", LONG)], "tools": [{"function": {"name": "f"}, "cache_control": {"type": "ephemeral"}}]},
        {"messages": [_msg("system", LONG)], "system": [{"text": LONG, "cache_control": {"type": "ephemeral"}}]},
    ],
)
def test_client_cache_control_anywhere_is_idempotent(extra: dict[str, Any]) -> None:
    payload = {"messages": [_msg("system", LONG), _msg("user", LONG), _msg("assistant", LONG), _msg("user", "q")], **extra}
    assert inject_anthropic_cache_control(payload) == payload


def test_input_never_mutated() -> None:
    messages = [_msg("system", LONG), _msg("user", LONG), _msg("assistant", LONG), _msg("user", "q")]
    payload = {"messages": messages, "model": "claude-haiku-5-5"}
    before = copy.deepcopy(payload)
    out = inject_anthropic_cache_control(payload)
    assert payload == before
    assert out is not payload
    assert _count_breakpoints(out) == 2


def test_breakpoints_never_exceed_two() -> None:
    messages = [_msg("system", LONG)] + [_msg("user" if i % 2 else "assistant", LONG) for i in range(8)]
    out = inject_anthropic_cache_control({"messages": messages})
    assert _count_breakpoints(out) <= 2


# ---- интеграция apply_passthrough_transforms ------------------------------------------


def _stubs(params: dict[str, Any]) -> tuple[Any, Any, Any]:
    route = SimpleNamespace(
        model={"backend": "opencode-go-claude"}, request={}, alias_effort=None,
        model_id="claude-haiku-5-5", handler=SimpleNamespace(headers={}),
    )
    return route, SimpleNamespace(request={}), SimpleNamespace(config={"params": params})


def _prepared() -> dict[str, Any]:
    return {"model": "claude-haiku-5-5", "messages": [_msg("system", LONG), _msg("user", "hi")]}


def test_flag_off_default_no_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FLAG_ANTHROPIC_CACHE_CONTROL, raising=False)
    route, body, adapter = _stubs({"cache_control_strategy": STRATEGY_ANTHROPIC_EPHEMERAL})
    prepared = _prepared()
    out = apply_passthrough_transforms(prepared, route, body, adapter)
    assert _count_breakpoints(out) == 0
    assert out == prepared


def test_flag_on_with_strategy_injects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG_ANTHROPIC_CACHE_CONTROL, "1")
    route, body, adapter = _stubs({"cache_control_strategy": STRATEGY_ANTHROPIC_EPHEMERAL})
    out = apply_passthrough_transforms(_prepared(), route, body, adapter)
    assert _count_breakpoints(out) == 1
    assert out["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_flag_on_without_strategy_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG_ANTHROPIC_CACHE_CONTROL, "1")
    route, body, adapter = _stubs({"strip_always": ["thinking"]})
    prepared = _prepared()
    assert apply_passthrough_transforms(prepared, route, body, adapter) == prepared


# ---- params: валидация / extract / sidecar --------------------------------------------


def test_validate_backend_params_strategy() -> None:
    assert validate_backend_params({"cache_control_strategy": None}) == ""
    assert validate_backend_params({"cache_control_strategy": "anthropic_ephemeral"}) == ""
    assert validate_backend_params({"cache_control_strategy": "bogus"}) == BACKEND_PARAMS_INVALID
    assert validate_backend_params({"cache_control_strategy": 5}) == BACKEND_PARAMS_INVALID


def test_extract_backend_params_omits_none_strategy() -> None:
    manifest = SimpleNamespace(params=ParamsConfig(strip_always=("thinking",)))
    params = extract_backend_params(manifest)["params"]
    assert "cache_control_strategy" not in params
    assert extract_backend_params(SimpleNamespace(params=ParamsConfig())) == {}


def test_extract_backend_params_includes_strategy() -> None:
    manifest = SimpleNamespace(params=ParamsConfig(cache_control_strategy="anthropic_ephemeral"))
    params = extract_backend_params(manifest)["params"]
    assert params["cache_control_strategy"] == "anthropic_ephemeral"


def test_serialize_sidecar_params() -> None:
    base = serialize_sidecar_params(ParamsConfig())
    assert base["tool_emulation"] is True
    assert "cache_control_strategy" not in base
    with_strategy = serialize_sidecar_params(ParamsConfig(cache_control_strategy="anthropic_ephemeral"))
    assert with_strategy["cache_control_strategy"] == "anthropic_ephemeral"


# ---- манифест opencode-go-claude -------------------------------------------------------


def test_opencode_manifest_loads_with_strategy() -> None:
    loaded = load_manifests(None, ADAPTER_KINDS)
    assert "opencode-go-claude" not in loaded.rejected_providers
    manifest = next(m for m in loaded.manifests if m.provider_id == "opencode-go-claude")
    assert manifest.params.cache_control_strategy == "anthropic_ephemeral"


def test_opencode_manifest_invalid_strategy_rejected(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parent.parent / "providers.d" / "opencode-go-claude.yaml"
    text = source.read_text(encoding="utf-8").replace(
        "cache_control_strategy: anthropic_ephemeral", "cache_control_strategy: bogus"
    )
    (tmp_path / "opencode-go-claude.yaml").write_text(text, encoding="utf-8")
    loaded = load_manifests(tmp_path, ADAPTER_KINDS)
    assert "provider_manifest_invalid" in loaded.rejected_providers.get("opencode-go-claude", ())
    assert all(m.provider_id != "opencode-go-claude" for m in loaded.manifests)

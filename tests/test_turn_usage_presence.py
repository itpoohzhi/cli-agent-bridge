"""Контракт usage хода: presence-признак, формат вывода и адаптер droid (без фантомных нулей)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from adapters.droid_adapter import DroidAdapter
from core.backend_adapter import TurnResult, Usage
from core.turn_dispatch import _format_turn_output
from core.usage_normalizer import Usage as NormalizerUsage
from core.usage_fields import (
    enrich_turn_usage_dict,
    normalize_usage_fields,
    telemetry_usage_updates,
)


def test_normalize_usage_fields_absent_is_none() -> None:
    assert normalize_usage_fields(None) == {
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "reasoning_tokens": None,
        "usage_present": None,
    }


def test_normalize_usage_fields_explicit_false() -> None:
    fields = normalize_usage_fields({"usage_present": False})
    assert fields["usage_present"] is False
    assert fields["input_tokens"] is None


def test_normalize_usage_fields_real_counters() -> None:
    assert normalize_usage_fields(
        {"input_tokens": 10, "output_tokens": 20, "cache_read_tokens": 3}
    ) == {
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_read_tokens": 3,
        "reasoning_tokens": None,
        "usage_present": True,
    }


def test_normalize_usage_fields_openai_aliases() -> None:
    fields = normalize_usage_fields({"prompt_tokens": 1, "completion_tokens": 2})
    assert fields["input_tokens"] == 1
    assert fields["output_tokens"] == 2
    assert fields["usage_present"] is True


def test_telemetry_usage_updates_absent_usage_only_flag() -> None:
    assert telemetry_usage_updates({"usage_present": False}) == {"usage_present": False}


def test_telemetry_usage_updates_real_counters() -> None:
    assert telemetry_usage_updates({"input_tokens": 10, "output_tokens": 20}) == {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "usage_present": True,
    }


def test_enrich_turn_usage_dict_overwrites_only_present_fields() -> None:
    turn_usage = SimpleNamespace(
        prompt_tokens=5,
        completion_tokens=None,
        cache_read_tokens=2,
        reasoning_tokens=None,
    )
    enriched = enrich_turn_usage_dict({"input_tokens": 1, "usage_present": False}, turn_usage)
    assert enriched == {"input_tokens": 5, "cache_read_tokens": 2, "usage_present": True}


def test_format_turn_output_usage_absent() -> None:
    out = _format_turn_output(TurnResult(text="hi"), "cli")
    assert out["usage"]["usage_present"] is False
    assert telemetry_usage_updates(out["usage"]) == {"usage_present": False}


def test_format_turn_output_usage_zero_counters_present() -> None:
    out = _format_turn_output(TurnResult(text="hi", usage=NormalizerUsage(0, 0)), "cli")
    assert out["usage"]["usage_present"] is True


def test_format_turn_output_usage_counters_present() -> None:
    out = _format_turn_output(TurnResult(text="hi", usage=Usage(10, 20)), "cli")
    assert out["usage"]["usage_present"] is True
    assert out["usage"]["input_tokens"] == 10
    assert out["usage"]["output_tokens"] == 20


def test_format_turn_output_mock_usage_without_present_does_not_crash() -> None:
    result = SimpleNamespace(
        state="done",
        rc=0,
        text="hi",
        reasoning="",
        err="",
        usage=SimpleNamespace(input_tokens=3, output_tokens=4),
        tool_calls=(),
        events=None,
        turn_usage=None,
    )
    out = _format_turn_output(result, "cli")
    assert out["usage"]["input_tokens"] == 3
    assert out["usage"]["output_tokens"] == 4


@dataclass
class _FakeTranscript:
    system: str
    runnable: str
    items: tuple[object, ...]


@dataclass
class _FakeTurnContext:
    rpc: _FakeTranscript
    images: tuple[object, ...]
    handler: Any
    keepalive: object | None
    on_activity: object | None = None


class _FakeHandler:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    def _run_once(
        self, legacy: dict[str, Any], keepalive: Any, writer: Any
    ) -> dict[str, Any]:
        return self._raw


def _droid_turn(raw: dict[str, Any]) -> TurnResult:
    ctx = _FakeTurnContext(
        rpc=_FakeTranscript(system="", runnable="", items=()),
        images=(),
        handler=_FakeHandler(raw),
        keepalive=None,
    )
    adapter = object.__new__(DroidAdapter)
    return adapter.execute_turn(ctx, None)


def test_droid_adapter_empty_usage_means_absent() -> None:
    result = _droid_turn({"state": "done", "rc": 0, "text": "ok", "usage": {}})
    assert result.state == "done"
    assert result.text == "ok"
    assert _format_turn_output(result, "droid")["usage"]["usage_present"] is False


def test_droid_adapter_missing_usage_key_means_absent() -> None:
    result = _droid_turn({"state": "done", "rc": 0, "text": "ok"})
    assert _format_turn_output(result, "droid")["usage"]["usage_present"] is False


def test_droid_adapter_usage_without_numeric_keys_means_absent() -> None:
    result = _droid_turn(
        {"state": "done", "rc": 0, "text": "ok", "usage": {"source": "none"}}
    )
    assert _format_turn_output(result, "droid")["usage"]["usage_present"] is False


def test_droid_adapter_real_usage_is_present() -> None:
    result = _droid_turn(
        {"state": "done", "rc": 0, "text": "ok", "usage": {"input_tokens": 5, "output_tokens": 7}}
    )
    assert _format_turn_output(result, "droid")["usage"]["usage_present"] is True
    assert result.usage.input_tokens == 5
    assert result.usage.output_tokens == 7


def test_droid_adapter_partial_usage_is_present() -> None:
    result = _droid_turn(
        {"state": "done", "rc": 0, "text": "ok", "usage": {"cache_read_tokens": 4}}
    )
    assert _format_turn_output(result, "droid")["usage"]["usage_present"] is True
    assert result.usage.cache_read_tokens == 4

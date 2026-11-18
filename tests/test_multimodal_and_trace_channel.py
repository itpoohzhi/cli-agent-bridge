"""Тесты на устранение 503 route_unavailable для multimodal и настройку канала маркеров инструментов."""

import os
import sys
from pathlib import Path
root = str(Path(__file__).resolve().parents[1])
if root not in sys.path:
    sys.path.insert(0, root)
agy_path = str(Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge")
if agy_path not in sys.path:
    sys.path.insert(0, agy_path)

import pytest
from core.model_modalities import MULTIMODAL_MODELS, supports_images, model_modalities
from core.route_eligibility import EligibilityFacts, EligibilityRequest, RouteSpec, route_eligible
from agy_runtime.sse_stream_helpers import SseStreamSession


def test_multimodal_models_contains_gemini_3_8_flash():
    assert "gemini-3.8-flash" in MULTIMODAL_MODELS
    assert supports_images(model_id="gemini-3.8-flash") is True
    assert supports_images(model_id="gemini-3.8-flash-agy") is True
    assert supports_images(model_id="gemini-4-carbon") is True
    assert supports_images(model_id="gemini-4-carbon-agy") is True
    assert supports_images(model_id="gpt-6.1-sol") is True
    assert supports_images(model_entry={"input": ["text", "image"]}, model_id="custom-model") is True
    assert supports_images(model_entry={"input": ["text", "tools"]}, model_id="unknown-text-model") is False
    assert model_modalities(model_id="gemini-3.8-flash") == ["text", "image"]
    assert model_modalities(model_id="unknown-text-model") == ["text"]


def test_multimodal_route_eligibility_with_images():
    route = RouteSpec("route-1", "agy", 100, 1)
    facts = EligibilityFacts(
        ready=True,
        circuit_open=False,
        blocked_models=(),
        probe_age_s=0.0,
        max_stale_age_s=0.0,
        env_drift_keys=(),
        supports_images=supports_images(model_id="gemini-3.8-flash"),
        backend_kind="agy",
    )
    req_with_images = EligibilityRequest(
        model_id="gemini-3.8-flash",
        effort=None,
        role_ids=(),
        excluded=frozenset(),
        requires_images=True,
    )
    assert route_eligible(route, facts, req_with_images) is True

    facts_no_images = EligibilityFacts(
        ready=True,
        circuit_open=False,
        blocked_models=(),
        probe_age_s=0.0,
        max_stale_age_s=0.0,
        env_drift_keys=(),
        supports_images=False,
        backend_kind="agy",
    )
    assert route_eligible(route, facts_no_images, req_with_images) is False


def test_tool_trace_channel_configuration(monkeypatch):
    import io

    class DummyHandler:
        def __init__(self):
            self.emitted = []
            self.wfile = io.BytesIO()
        def _emit(self, text):
            self.emitted.append(text)
            return True

    handler = DummyHandler()
    ctx = {
        "turn_id": "t1",
        "conversation_id": "c1",
        "model": "test-model",
    }
    hooks = (lambda name, default=True: True, None, None, None)
    monkeypatch.setenv("AGY_BRIDGE_TOOL_TRACE_CHANNEL", "content")
    session = SseStreamSession(handler=handler, ctx=ctx, hooks=hooks)

    emitted_texts = []
    emitted_reasonings = []
    session.on_text = lambda text: emitted_texts.append(text) or True
    session.on_reasoning = lambda text: emitted_reasonings.append(text) or True

    event = {"event": "tool_finish", "tool_name": "run_command", "status": "done"}
    ok = session.on_tool_trace(event)
    assert ok is True
    assert len(emitted_texts) == 1
    assert len(emitted_reasonings) == 0
    assert emitted_texts[0].startswith("\n\n[🔧 tool:")
    assert emitted_texts[0].endswith("]\n\n")

    # Now test default channel (reasoning)
    ctx_default = {
        "turn_id": "t1",
        "conversation_id": "c1",
        "model": "test-model",
    }
    monkeypatch.delenv("AGY_BRIDGE_TOOL_TRACE_CHANNEL", raising=False)
    session_default = SseStreamSession(handler=handler, ctx=ctx_default, hooks=hooks)
    emitted_texts.clear()
    emitted_reasonings.clear()
    session_default.on_text = lambda text: emitted_texts.append(text) or True
    session_default.on_reasoning = lambda text: emitted_reasonings.append(text) or True

    ok2 = session_default.on_tool_trace(event)
    assert ok2 is True
    assert len(emitted_texts) == 0
    assert len(emitted_reasonings) == 1
    assert "🔧 tool:" in emitted_reasonings[0]

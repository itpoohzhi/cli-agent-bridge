"""Смена модели в сессии: `gemini-4-carbon` без оси effort (`efforts == ["off"]`), кламп и отказы CLI.

L1: чистая политика (`core.effortless_policy`, `core.cli_rejection`, passthrough-подготовка).
L2: хаб `:9882` с fake upstream и настоящий `agy-bridge` с фейковым CLI (argv фиксируется).
"""

from __future__ import annotations

import http.client
import importlib
import json
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from core.backend_adapter import AdapterRegistry  # noqa: E402
from core.cli_rejection import ENV_DETERMINISTIC_RE, is_deterministic_cli_rejection  # noqa: E402
from core.effort_policy import EffortResolution, ModelEffortCardFields, ModelEffortSpec  # noqa: E402
from core.effortless_policy import (  # noqa: E402
    EffortDecision,
    card_effort_fields,
    effort_cli_args,
    effortless_specs,
    is_effortless,
    resolve_request_effort,
    strip_effortless_effort,
)
from core.passthrough_autonomy import prepare_passthrough_request  # noqa: E402

res = importlib.import_module("test_agy_bridge_resilience")

CARBON, ARGON, HYDROGEN = "gemini-4-carbon", "gemini-4-argon", "gemini-4-hydrogen"
FLAG = "BRIDGE_EFFORT_CATALOG_ENABLED"
CLAMP_FLAG = "BRIDGE_EFFORTLESS_CLAMP_ENABLED"
LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
OFF_MODEL = {"efforts": ["off"], "default_effort": "off"}
LADDER_MODEL = {"efforts": ["low", "medium", "high"], "default_effort": "high"}
# (модель, запрошенный effort, ожидаемый хвост `--effort` в argv, ожидаемый `reasoning_effort` у upstream хаба)
TURNS = (
    (HYDROGEN, "xhigh", ["--effort", "xhigh"], "xhigh"),
    (CARBON, "high", [], None),
    (CARBON, "medium", [], None),
    (ARGON, "medium", ["--effort", "medium"], "medium"),
)
REJECT = 'invalid model selection (--model "gemini-4-carbon" --effort "high"): --effort is not supported for model "gemini-4-carbon"'


# ---- L1: политика effort и классификатор отказов CLI ------------------------------


def test_is_effortless_only_for_off_ladder() -> None:
    assert is_effortless(["off"]) and is_effortless(["OFF"])
    assert not any(map(is_effortless, (["low", "high"], [], None, ["off", "low"], "off")))


def test_specs_card_fields_and_cli_args() -> None:
    specs = {"a": ModelEffortSpec(("off",), "off"), "b": ModelEffortSpec(("low", "high"), "high")}
    assert set(effortless_specs(specs)) == {"a"}
    off_card = card_effort_fields(ModelEffortCardFields("off", ("off",)))
    assert off_card == {"supports_thinking": False, "supported_reasoning_efforts": ["off"], "default_reasoning_effort": "off"}
    assert card_effort_fields(ModelEffortCardFields("high", ("low", "high")))["supports_thinking"] is True
    assert effort_cli_args("off") == effort_cli_args(None) == effort_cli_args("") == []
    assert effort_cli_args("high") == ["--effort", "high"]


@pytest.mark.parametrize("effort_on", [False, True])
def test_passthrough_strips_reasoning_effort_for_effortless_model(effort_on: bool) -> None:
    req = {"model": CARBON, "reasoning_effort": "high", "messages": []}
    clean, resolution = prepare_passthrough_request(req, OFF_MODEL, CARBON, effort_on=effort_on)
    assert "reasoning_effort" not in clean and clean["messages"] == []
    assert (resolution.value, resolution.apply) == ("off", True)
    assert resolution.clamped_from == (None if effort_on else "high")
    assert req["reasoning_effort"] == "high"  # исходный запрос не мутируется


def test_passthrough_keeps_request_of_ordinary_model() -> None:
    req = {"model": ARGON, "reasoning_effort": "high"}
    clean, resolution = prepare_passthrough_request(req, LADDER_MODEL, ARGON, effort_on=False)
    assert clean == req and resolution == EffortResolution()
    spec = ModelEffortSpec(("low", "medium", "high"), "high")
    assert strip_effortless_effort(req, spec, resolution) == (req, resolution)


@pytest.mark.parametrize("raw", ["high", "xhigh"])
def test_resolve_request_effort_clamps_known_level_to_off(raw: str) -> None:
    decision = resolve_request_effort(raw, OFF_MODEL, LEVELS, clamp_enabled=True)
    assert decision == EffortDecision("off", "clamped", None)
    assert resolve_request_effort(None, OFF_MODEL, LEVELS).effort == "off"
    assert resolve_request_effort("off", OFF_MODEL, LEVELS) == EffortDecision("off", "request", None)


def test_resolve_request_effort_rejects_when_clamp_disabled_or_junk(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_request_effort("high", OFF_MODEL, LEVELS, clamp_enabled=False).error
    monkeypatch.setenv(CLAMP_FLAG, "false")
    assert resolve_request_effort("high", OFF_MODEL, LEVELS).error
    assert resolve_request_effort("ultra_turbo", OFF_MODEL, LEVELS, clamp_enabled=True).error
    assert resolve_request_effort(7, OFF_MODEL, LEVELS).error == "reasoning_effort must be a string"
    assert resolve_request_effort("off", LADDER_MODEL, LEVELS, clamp_enabled=True).error


@pytest.mark.parametrize(
    "message", ["Invalid model selection: x", 'effort "high" is not supported for model "m"', "flag requires --effort"]
)
def test_default_deterministic_patterns(message: str) -> None:
    assert is_deterministic_cli_rejection(message, {})
    assert not is_deterministic_cli_rejection("connection reset by peer", {})
    assert not is_deterministic_cli_rejection(None, {}) and not is_deterministic_cli_rejection("", {})


def test_deterministic_pattern_from_env_and_broken_regex_fallback() -> None:
    assert is_deterministic_cli_rejection("quota exceeded", {ENV_DETERMINISTIC_RE: "quota"})
    assert not is_deterministic_cli_rejection(REJECT, {ENV_DETERMINISTIC_RE: "quota"})
    assert is_deterministic_cli_rejection(REJECT, {ENV_DETERMINISTIC_RE: "[unclosed"})
    assert not is_deterministic_cli_rejection("boom", {ENV_DETERMINISTIC_RE: "[unclosed"})


# ---- L2: хаб :9882 с fake upstream ------------------------------------------------


@contextmanager
def _serve(handler: type[BaseHTTPRequestHandler]) -> Iterator[int]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield httpd.server_port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _call(port: int, path: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    head = {"Authorization": "Bearer hub-key", "Connection": "close", "Content-Type": "application/json", **(headers or {})}
    try:
        conn.request("GET" if body is None else "POST", path, None if body is None else json.dumps(body), head)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[SimpleNamespace]:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    seen: list[dict[str, Any]] = []

    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(request)
            reply = {"id": "c1", "object": "chat.completion", "created": 1, "model": request["model"],
                     "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]}
            body = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    with ExitStack() as stack:
        upstream_port = stack.enter_context(_serve(Upstream))
        raw = json.loads((ROOT / "fleet.json").read_text())
        raw["models"] = [m for m in raw["models"] if m["backend"] == "agy"]
        raw["aliases"] = {k: v for k, v in raw["aliases"].items() if v["backend"] == "agy"}
        raw["default_model"] = ARGON
        raw["backends"] = {"agy": {**raw["backends"]["agy"], "base_url": f"http://127.0.0.1:{upstream_port}/v1"}}
        catalog = server._build_catalog(raw)
        backends = AdapterRegistry.from_fleet(catalog, ADAPTER_KINDS, lambda: catalog, server)
        for name, value in (("FLEET", catalog), ("BACKENDS", backends), ("MODEL_ID", ARGON), ("_shutting_down", False),
                            ("_is_drain_enabled", lambda: False), ("ADVERTISED_EFFORT_ALIASES", tuple(raw["aliases"])),
                            ("_EFFORT_SPECS_CACHE", (None, {})),
                            ("TOKEN_CACHE", server.TokenCache(path=tmp_path / ".env", environ={"BRIDGE_KEY": "hub-key"}))):
            monkeypatch.setattr(server, name, value)
        for adapter in backends.adapters():
            stack.callback(adapter.shutdown)
        port = stack.enter_context(_serve(server.Handler))
        yield SimpleNamespace(port=port, seen=seen, aliases=tuple(raw["aliases"]))


def _chat(hub: SimpleNamespace, model: str, effort: str) -> Any:
    body = {"model": model, "reasoning_effort": effort, "messages": [{"role": "user", "content": "hi"}]}
    return _call(hub.port, "/v1/chat/completions", body, {"x-dsh-chat-id": "switch-chat"})


@pytest.mark.parametrize("flag", ["false", "true"])
def test_hub_models_advertise_carbon_without_effort_axis(
    hub: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    monkeypatch.setenv(FLAG, flag)
    status, payload = _call(hub.port, "/v1/models")
    cards = {card["id"]: card for card in payload["data"]}
    assert status == 200 and not hub.seen
    assert cards[CARBON]["supports_thinking"] is False
    assert cards[CARBON]["supported_reasoning_efforts"] == ["off"]
    assert cards[CARBON]["default_reasoning_effort"] == "off"
    assert not {f"{CARBON}-{level}" for level in ("low", "medium", "high")} & set(cards)
    if flag == "true":
        assert cards[ARGON]["supported_reasoning_efforts"] == ["low", "medium", "high"]


@pytest.mark.parametrize("flag", ["false", "true"])
def test_hub_chat_drops_reasoning_effort_for_carbon_only(
    hub: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    monkeypatch.setenv(FLAG, flag)
    status, payload = _chat(hub, CARBON, "high")
    assert status == 200, payload
    assert hub.seen[-1]["model"] == CARBON and "reasoning_effort" not in hub.seen[-1]
    assert _chat(hub, ARGON, "high")[0] == 200
    assert hub.seen[-1]["model"] == ARGON and hub.seen[-1]["reasoning_effort"] == "high"


def test_hub_removed_carbon_suffix_aliases_are_gone(hub: SimpleNamespace) -> None:
    assert not any(alias.startswith(f"{CARBON}-") for alias in hub.aliases)
    assert f"{HYDROGEN}-high" in hub.aliases
    assert _chat(hub, f"{CARBON}-high", "high")[0] == 200  # обратная совместимость клиентов со старым id
    assert "reasoning_effort" not in hub.seen[-1] and hub.seen[-1]["model"] == CARBON


def test_hub_four_turn_model_switch_isolates_effort(hub: SimpleNamespace) -> None:
    for model, effort, _, upstream_effort in TURNS:
        assert _chat(hub, model, effort)[0] == 200, model
        assert hub.seen[-1]["model"] == model
        assert hub.seen[-1].get("reasoning_effort") == upstream_effort, (model, effort)
    assert len(hub.seen) == len(TURNS)


# ---- L2: agy-bridge с фейковым CLI -------------------------------------------------

CIDS = ("82188e72-6eca-4f23-a0b3-2257ec43bd60", "fa92a264-8039-40dc-a716-37f7f64ea9e3",
        "57172100-e4cf-4553-a0b6-f0af14c28a80", "0d4c2a9e-33a5-4c0e-9d57-6f3b8f1f9a11")


@pytest.fixture
def agy() -> Iterator[SimpleNamespace]:
    with res._Fixture() as fx:
        bridge = res._HttpBridge()
        try:
            yield SimpleNamespace(fx=fx, bridge=bridge)
        finally:
            bridge.close()


def _turn(agy: SimpleNamespace, model: str, effort: str, history: bool = False) -> tuple[int, dict[str, Any]]:
    body = res._agentic_body("ход " + model, history, chat_id="")
    body.update(model=model, reasoning_effort=effort)
    return res._post_with_headers(agy.bridge, body, {"x-dsh-chat-id": "switch-chat"})


def _effort_tail(argv: list[str]) -> list[str]:
    return argv[argv.index("--effort"):][:2] if "--effort" in argv else []


def test_agy_bridge_omits_effort_flag_for_effortless_model(agy: SimpleNamespace) -> None:
    agy.fx.write_scenario([], spawns=[res._quick(CIDS[0]), res._quick(CIDS[1])])
    assert _turn(agy, CARBON, "high")[0] == 200
    assert _turn(agy, ARGON, "high")[0] == 200
    carbon, argon = agy.fx.spawns()
    assert carbon[carbon.index("--model") + 1] == CARBON and "--effort" not in carbon
    assert argon[argon.index("--model") + 1] == ARGON and _effort_tail(argon) == ["--effort", "high"]


def test_agy_bridge_deterministic_cli_rejection_is_not_retried(agy: SimpleNamespace) -> None:
    failing = [res._init_ev(0.05, CIDS[0]), res._result_ev(0.1, CIDS[0], "ERROR", REJECT), res._exit_ev(0.15, 1)]
    agy.fx.write_scenario([], spawns=[failing, res._quick(CIDS[1])])
    started = time.monotonic()
    status, payload = _turn(agy, CARBON, "high")
    assert status >= 400, payload
    assert len(agy.fx.spawns()) == 1  # attempts == 1: повтор и фолбэк бессмысленны
    assert time.monotonic() - started < 10


def test_agy_bridge_four_turn_switch_keeps_effort_isolated(agy: SimpleNamespace) -> None:
    agy.fx.write_scenario([], spawns=[res._quick(cid) for cid in CIDS])
    results = [_turn(agy, model, effort, history=index > 0) for index, (model, effort, _, _) in enumerate(TURNS)]
    assert [status for status, _ in results] == [200] * len(TURNS)
    spawns = agy.fx.spawns()
    for argv, (model, _, expected, _) in zip(spawns, TURNS, strict=True):
        assert argv[argv.index("--model") + 1] == model
        assert _effort_tail(argv) == expected, model
    assert "--conversation" not in spawns[1]  # Carbon не наследует разговор Hydrogen
    assert "--conversation" not in spawns[3]  # Argon не наследует разговор Carbon

"""L2 смены модели в сессии: хаб `:9882` с fake upstream и настоящий `agy-bridge` с фейковым CLI (argv фиксируется).

L1-политика effort и классификатор отказов CLI — в `tests/test_session_model_switch.py`.
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

res = importlib.import_module("test_agy_bridge_resilience")

CARBON, ARGON, HYDROGEN = "gemini-4-carbon", "gemini-4-argon", "gemini-4-hydrogen"
FLAG = "BRIDGE_EFFORT_CATALOG_ENABLED"
# (модель, запрошенный effort, ожидаемый хвост `--effort` в argv, ожидаемый `reasoning_effort` у upstream хаба)
TURNS = (
    (HYDROGEN, "xhigh", ["--effort", "xhigh"], "xhigh"),
    (CARBON, "high", [], None),
    (CARBON, "medium", [], None),
    (ARGON, "medium", ["--effort", "medium"], "medium"),
)
REJECT = 'invalid model selection (--model "gemini-4-carbon" --effort "high"): --effort is not supported for model "gemini-4-carbon"'


# ---- хаб :9882 с fake upstream ------------------------------------------------


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

        def log_message(self, format: str, *args: object) -> None:
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


@pytest.mark.parametrize("bad_effort", ["ultra_turbo", 123, None])
def test_hub_rejects_invalid_and_non_string_effort_for_carbon(
    hub: SimpleNamespace, bad_effort: object
) -> None:
    body = {"model": CARBON, "reasoning_effort": bad_effort, "messages": [{"role": "user", "content": "hi"}]}
    status, payload = _call(hub.port, "/v1/chat/completions", body, {"x-dsh-chat-id": "switch-chat"})
    assert status == 400
    assert payload["error"]["type"] == "unsupported_reasoning_effort"
    assert not hub.seen


def test_hub_rejects_effort_on_carbon_when_clamp_disabled(
    hub: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRIDGE_EFFORTLESS_CLAMP_ENABLED", "false")
    status, payload = _chat(hub, CARBON, "high")
    assert status == 400
    assert payload["error"]["type"] == "unsupported_reasoning_effort"
    assert not hub.seen
    ok_status, _ = _chat(hub, CARBON, "OFF")
    assert ok_status == 200 and "reasoning_effort" not in hub.seen[-1]
    bare_status, _ = _call(
        hub.port,
        "/v1/chat/completions",
        {"model": CARBON, "messages": [{"role": "user", "content": "hi"}]},
        {"x-dsh-chat-id": "switch-chat"},
    )
    assert bare_status == 200 and "reasoning_effort" not in hub.seen[-1]


# ---- agy-bridge с фейковым CLI -------------------------------------------------

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


def _failing(error: str) -> list[dict[str, object]]:
    return [res._init_ev(0.05, CIDS[0]), res._result_ev(0.1, CIDS[0], "ERROR", error), res._exit_ev(0.15, 1)]


def test_agy_bridge_hot_deterministic_cli_rejection_is_not_cold_retried(agy: SimpleNamespace) -> None:
    agy.fx.write_scenario([], spawns=[res._quick(CIDS[0]), _failing(REJECT), res._quick(CIDS[1])])
    assert _turn(agy, ARGON, "high")[0] == 200
    status, payload = _turn(agy, ARGON, "high", history=True)
    assert status >= 400, payload
    spawns = agy.fx.spawns()
    assert len(spawns) == 2  # горячий отказ CLI детерминирован: холодного повтора нет
    assert "--conversation" in spawns[1]


def test_agy_bridge_hot_agy_error_falls_back_cold_without_retry_pause(agy: SimpleNamespace) -> None:
    pauses: list[int] = []
    agy.fx.patch("_retry_pause_s", lambda attempt, rng=None: pauses.append(attempt) or 0.0)
    agy.fx.write_scenario([], spawns=[res._quick(CIDS[0]), _failing("transient glitch"), res._quick(CIDS[1])])
    assert _turn(agy, ARGON, "high")[0] == 200
    assert _turn(agy, ARGON, "high", history=True)[0] == 200
    spawns = agy.fx.spawns()
    assert len(spawns) == 3 and "--conversation" in spawns[1] and "--conversation" not in spawns[2]
    assert pauses == []  # мгновенный холодный фолбэк горячей сессии идёт мимо общего backoff-повтора


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


def test_agy_bridge_pump_error_is_retried_even_if_err_matches_rejection_re(
    agy: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = res._bridge()
    assert bridge._is_cli_rejection_outcome({"state": "pump_error", "err": REJECT}) is False
    assert bridge._is_cli_rejection_outcome({"state": "agy_error", "err": REJECT}) is True
    agy.fx.patch("_retry_pause_s", lambda _attempt, rng=None: 0.0)
    orig_execute = bridge.Handler._execute
    calls = 0

    def execute_with_first_pump_error(self: Any, *args: Any, **kwargs: Any) -> dict[str, object]:
        nonlocal calls
        calls += 1
        result = orig_execute(self, *args, **kwargs)
        if calls == 1:
            return {**result, "state": "pump_error", "rc": 1, "text": "", "err": REJECT}
        return result

    monkeypatch.setattr(bridge.Handler, "_execute", execute_with_first_pump_error)
    agy.fx.write_scenario([], spawns=[res._quick(CIDS[0]), res._quick(CIDS[1])])
    status, payload = _turn(agy, CARBON, "high")
    assert status == 200, payload
    assert calls == 2 and len(agy.fx.spawns()) == 2

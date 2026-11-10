"""L1-тесты узкого адаптера параметров (core/param_adapter.py)."""

from __future__ import annotations

import json

import pytest

from core import param_adapter as pa

ERR_EFFORT = json.dumps(
    {"error": {"message": "Unsupported parameter: 'reasoning_effort' for this model"}}
).encode()
ERR_TEMP = json.dumps(
    {"error": {"message": "temperature is not supported with this model"}}
).encode()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "BRIDGE_PARAM_ADAPTER_WHITELIST",
        "BRIDGE_PARAM_ADAPTER_ERROR_PATTERN",
        "BRIDGE_PARAM_PROFILE_TTL_S",
        "BRIDGE_QUORUM_ROLE_PREFIXES",
        "BRIDGE_STATE_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


SENT = {"model": "m", "reasoning_effort": "high", "temperature": 0.2}


@pytest.mark.parametrize("status", [400, 422])
def test_named_whitelist_param_retry_without(status):
    d = pa.decide(
        status, ERR_EFFORT, SENT, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False
    )
    assert d == pa.RetryWithout("reasoning_effort")


def test_retry_saves_profile_and_apply_profile(tmp_path):
    clock = Clock()
    store = pa.ParamProfileStore(
        tmp_path / "param-profiles.json", ttl_s=100, clock=clock
    )
    assert not store.get("p", "m", "fp")
    profile = store.record_drop("p", "m", "fp", "reasoning_effort")
    assert profile.dropped == ("reasoning_effort",)
    assert (tmp_path / "param-profiles.json").exists()
    # новый экземпляр читает с диска
    again = pa.ParamProfileStore(
        tmp_path / "param-profiles.json", ttl_s=100, clock=clock
    ).get("p", "m", "fp")
    assert again.drops("reasoning_effort")
    assert not store.get("p", "m", "other-fp")
    out = pa.apply_profile(SENT, again)
    assert "reasoning_effort" not in out and out["temperature"] == 0.2
    assert "reasoning_effort" in SENT  # вход не мутирован


def test_profile_ttl_expiry(tmp_path):
    clock = Clock()
    store = pa.ParamProfileStore(tmp_path / "pp.json", ttl_s=50, clock=clock)
    store.record_drop("p", "m", "fp", "top_p")
    clock.now += 49
    assert store.get("p", "m", "fp").drops("top_p")
    clock.now += 2
    assert not store.get("p", "m", "fp")


def test_store_default_path_uses_state_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("BRIDGE_PARAM_PROFILE_TTL_S", "7")
    store = pa.ParamProfileStore(clock=Clock())
    assert store.path == tmp_path / "param-profiles.json"
    store.record_drop("p", "m", "fp", "effort")
    data = json.loads(store.path.read_text())
    meta = data["profiles"]["(p|m|fp)"]["effort"]
    assert meta["action"] == "drop" and meta["expires_at"] - meta["learned_at"] == 7


def test_corrupt_profile_file_is_ignored(tmp_path):
    path = tmp_path / "pp.json"
    path.write_text("{not json")
    store = pa.ParamProfileStore(path, ttl_s=10, clock=Clock())
    assert not store.get("p", "m", "fp")
    assert store.record_drop("p", "m", "fp", "top_p").drops("top_p")


def test_no_named_param_passthrough():
    body = json.dumps(
        {"error": {"message": "invalid request: messages required"}}
    ).encode()
    assert isinstance(
        pa.decide(400, body, SENT, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False),
        pa.Passthrough,
    )


@pytest.mark.parametrize("status", [200, 401, 429, 500, 502, 503, 504, 0])
def test_other_statuses_fail_fast(status):
    d = pa.decide(
        status, ERR_EFFORT, SENT, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False
    )
    assert isinstance(d, pa.Passthrough)


def test_quorum_effort_degraded():
    assert pa.is_quorum_call("coder-1", None)
    d = pa.decide(422, ERR_EFFORT, SENT, pa.ParamProfile(), pa.GLOBAL_WHITELIST, True)
    assert d == pa.Degraded("reasoning_effort")
    status, body, headers = pa.degraded_response("reasoning_effort", "mid")
    assert status == 422
    assert body == {
        "error": {"type": "param_degraded", "param": "reasoning_effort", "model": "mid"}
    }
    assert headers == {"X-Bridge-Degraded": "reasoning_effort"}
    assert pa.adapted_headers("top_p") == {"X-Bridge-Param-Adapted": "top_p"}


def test_quorum_temperature_retry_without():
    d = pa.decide(400, ERR_TEMP, SENT, pa.ParamProfile(), pa.GLOBAL_WHITELIST, True)
    assert d == pa.RetryWithout("temperature")


def test_ambiguous_two_params_passthrough():
    body = b"unsupported parameters: reasoning_effort, temperature"
    assert isinstance(
        pa.decide(400, body, SENT, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False),
        pa.Passthrough,
    )


def test_param_not_in_sent_passthrough():
    sent = {"model": "m", "temperature": 0.1}
    assert isinstance(
        pa.decide(400, ERR_EFFORT, sent, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False),
        pa.Passthrough,
    )


def test_effort_not_confused_with_reasoning_effort():
    sent = {"effort": "low"}
    assert isinstance(
        pa.decide(400, ERR_EFFORT, sent, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False),
        pa.Passthrough,
    )


def test_whitelist_env_narrowing(monkeypatch):
    monkeypatch.setenv("BRIDGE_PARAM_ADAPTER_WHITELIST", "temperature,bogus_param")
    wl = pa.resolve_whitelist()
    assert wl == ("temperature",)  # расширять нельзя
    assert isinstance(
        pa.decide(400, ERR_EFFORT, SENT, pa.ParamProfile(), wl, False), pa.Passthrough
    )
    assert pa.decide(
        400, ERR_TEMP, SENT, pa.ParamProfile(), wl, False
    ) == pa.RetryWithout("temperature")


def test_error_pattern_env_override(monkeypatch):
    body = b"parameter 'top_p' blorp"
    sent = {"top_p": 0.5}
    assert isinstance(
        pa.decide(400, body, sent, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False),
        pa.Passthrough,
    )
    monkeypatch.setenv("BRIDGE_PARAM_ADAPTER_ERROR_PATTERN", "blorp")
    assert pa.decide(
        400, body, sent, pa.ParamProfile(), pa.GLOBAL_WHITELIST, False
    ) == pa.RetryWithout("top_p")


def test_is_quorum_call(monkeypatch):
    assert pa.is_quorum_call("reviewer-abc-1", None)
    assert pa.is_quorum_call("CODER-9", "")
    assert not pa.is_quorum_call("explorer-1", None)
    assert not pa.is_quorum_call(None, None)
    assert not pa.is_quorum_call("", "other")
    assert pa.is_quorum_call(None, "Zero-Canon")
    assert pa.is_quorum_call("explorer-1", "Zero-Canon")
    assert pa.is_quorum_call("x-1", None, prefixes=["x"])
    monkeypatch.setenv("BRIDGE_QUORUM_ROLE_PREFIXES", "explorer")
    assert pa.is_quorum_call("explorer-1", None)
    assert not pa.is_quorum_call("coder-1", None)


def test_strip_always():
    body = {"a": 1, "b": 2}
    assert pa.strip_always(body, ["a"]) == {"b": 2}
    assert body == {"a": 1, "b": 2}


def test_normalize_effort_field_rename():
    body = {"reasoning_effort": "high", "messages": []}
    out = pa.normalize_params(body, effort_field="effort", effort_map={}, strip=[])
    assert out == {"effort": "high", "messages": []}
    assert "reasoning_effort" in body


def test_normalize_effort_none_and_map_patch():
    body = {"effort": "high"}
    assert pa.normalize_params(body, effort_field="none", effort_map={}, strip=[]) == {}
    emap = {"high": {"thinking": {"type": "enabled", "budget_tokens": 8000}}}
    out = pa.normalize_params(body, effort_field="none", effort_map=emap, strip=[])
    assert out == {"thinking": {"type": "enabled", "budget_tokens": 8000}}
    out["thinking"]["budget_tokens"] = 1
    assert emap["high"]["thinking"]["budget_tokens"] == 8000  # карта не загрязнена


def test_normalize_effort_unmapped_value_uses_field():
    out = pa.normalize_params(
        {"effort": "weird"},
        effort_field="reasoning_effort",
        effort_map={"high": {}},
        strip=[],
    )
    assert out == {"reasoning_effort": "weird"}


def test_normalize_numbers_and_strip():
    body = {"temperature": "0.7", "top_p": 5, "max_tokens": "128", "keep": 1, "drop": 2}
    out = pa.normalize_params(body, effort_field="none", effort_map={}, strip=["drop"])
    assert out == {"temperature": 0.7, "top_p": 1.0, "max_tokens": 128, "keep": 1}
    out = pa.normalize_params(
        {"temperature": 9, "top_p": -1}, effort_field="none", effort_map={}, strip=[]
    )
    assert out == {"temperature": 2.0, "top_p": 0.0}
    bad = {"temperature": "hot", "top_p": True, "max_tokens": 0}
    assert pa.normalize_params(bad, effort_field="none", effort_map={}, strip=[]) == {}
    assert (
        pa.normalize_params(
            {"max_tokens": -5}, effort_field="none", effort_map={}, strip=[]
        )
        == {}
    )
    assert (
        pa.normalize_params(
            {"max_tokens": 1.5}, effort_field="none", effort_map={}, strip=[]
        )
        == {}
    )


def test_normalize_stop():
    kw = dict(effort_field="none", effort_map={}, strip=[])
    assert pa.normalize_params({"stop": "END"}, **kw) == {"stop": "END"}
    assert pa.normalize_params({"stop": list("abcdef")}, **kw) == {"stop": list("abcd")}
    assert pa.normalize_params({"stop": ["a", 1, "", "b"]}, **kw) == {
        "stop": ["a", "b"]
    }
    assert pa.normalize_params({"stop": []}, **kw) == {}
    assert pa.normalize_params({"stop": 5}, **kw) == {}


def test_normalize_tools():
    kw = dict(effort_field="none", effort_map={}, strip=[])
    assert pa.normalize_params({"tools": [], "tool_choice": "auto"}, **kw) == {}
    assert pa.normalize_params({"tool_choice": "auto"}, **kw) == {}
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    body = {
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "f"}},
    }
    assert pa.normalize_params(body, **kw) == body

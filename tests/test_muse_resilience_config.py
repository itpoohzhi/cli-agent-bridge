import pytest

from adapters.muse_config import get_muse_timeouts, MuseTimeouts


def _resolve_proxy_port(config, env):
    # Explicit config has highest priority over env (REQ-001, RW-011).
    if config is not None and "proxy_port" in config:
        return config["proxy_port"]
    env_val = env.get("MUSE_PROXY_PORT")
    if env_val is not None:
        return int(env_val)
    return 10820


def test_proxy_port_precedence_and_frankfurt_default(monkeypatch):
    # No config, no env -> default Frankfurt port 10820
    monkeypatch.delenv("MUSE_PROXY_PORT", raising=False)
    assert _resolve_proxy_port(None, {}) == 10820

    # Env set, no config -> env wins
    monkeypatch.setenv("MUSE_PROXY_PORT", "10840")
    assert _resolve_proxy_port({}, {"MUSE_PROXY_PORT": "10840"}) == 10840

    # Env set AND explicit config -> explicit config wins
    assert (
        _resolve_proxy_port({"proxy_port": 10830}, {"MUSE_PROXY_PORT": "10840"})
        == 10830
    )


def test_get_muse_timeouts_defaults(monkeypatch):
    for key in (
        "MUSE_STREAM_WRITE_TIMEOUT_S",
        "MUSE_LIVE_WRITE_TIMEOUT_S",
        "MUSE_CONTROL_WRITE_TIMEOUT_S",
        "MUSE_WRITES_QUEUE_MAX",
        "MUSE_WRITES_QUEUE_PUT_TIMEOUT_S",
    ):
        monkeypatch.delenv(key, raising=False)

    timeouts = get_muse_timeouts()
    assert isinstance(timeouts, MuseTimeouts)
    assert timeouts.stream_write_timeout_s == 30.0
    assert timeouts.live_write_timeout_s == 30.0
    assert timeouts.control_write_timeout_s == 15.0
    assert timeouts.writes_queue_max == 128
    assert timeouts.writes_queue_put_timeout_s == 5.0


def test_get_muse_timeouts_env_override(monkeypatch):
    monkeypatch.setenv("MUSE_STREAM_WRITE_TIMEOUT_S", "12.5")
    monkeypatch.setenv("MUSE_LIVE_WRITE_TIMEOUT_S", "7.5")
    monkeypatch.setenv("MUSE_CONTROL_WRITE_TIMEOUT_S", "3")
    monkeypatch.setenv("MUSE_WRITES_QUEUE_MAX", "64")
    monkeypatch.setenv("MUSE_WRITES_QUEUE_PUT_TIMEOUT_S", "2.5")

    timeouts = get_muse_timeouts()
    assert timeouts.stream_write_timeout_s == 12.5
    assert timeouts.live_write_timeout_s == 7.5
    assert timeouts.control_write_timeout_s == 3.0
    assert timeouts.writes_queue_max == 64
    assert timeouts.writes_queue_put_timeout_s == 2.5


@pytest.mark.parametrize(
    "value",
    ["not-a-number", "", "0", "-5", None],
)
def test_get_muse_timeouts_invalid_env_falls_back(monkeypatch, value):
    key = "MUSE_STREAM_WRITE_TIMEOUT_S"
    if value is None:
        monkeypatch.delenv(key, raising=False)
    else:
        monkeypatch.setenv(key, value)

    timeouts = get_muse_timeouts()
    assert timeouts.stream_write_timeout_s == 30.0

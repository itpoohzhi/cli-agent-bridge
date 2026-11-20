"""Unit-тесты для core/correlation_contract.py и agy_runtime/long_session_config.py (W1)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

from agy_runtime import long_session_config as lsc  # noqa: E402
from core.correlation_contract import (  # noqa: E402
    DEFAULT_CORR_MAX_LEN,
    build_validated_header,
    extract_correlation,
    format_log_corr_suffix,
    sanitize_corr_token,
)

_CID_RE = re.compile(r"^[0-9a-f-]{8,64}$")


def test_sanitize_corr_token_accepts_ascii_and_rejects_bad() -> None:
    assert DEFAULT_CORR_MAX_LEN == 64
    assert sanitize_corr_token("req-123_ABC.~!") == "req-123_ABC.~!"
    assert sanitize_corr_token("  req-1  ") == "req-1"
    assert sanitize_corr_token("") == "-"
    assert sanitize_corr_token(None) == "-"
    assert sanitize_corr_token(12345) == "-"
    assert sanitize_corr_token("bad\r\ninject") == "-"
    assert sanitize_corr_token("bad space") == "-"
    assert sanitize_corr_token("кириллица") == "-"
    assert sanitize_corr_token("a" * 64, max_len=64) == "a" * 64
    assert sanitize_corr_token("a" * 65, max_len=64) == "-"
    assert sanitize_corr_token("ab", max_len=0) == "-"
    assert sanitize_corr_token("a", max_len=0) == "a"


def test_extract_and_format_correlation_and_header() -> None:
    req_id, sub_id = extract_correlation(
        {"X-Request-Id": "req-01", "x-subagent-id": "sub-02"}
    )
    assert (req_id, sub_id) == ("req-01", "sub-02")
    assert format_log_corr_suffix("req-01", "sub-02") == " req_id=req-01 sub_id=sub-02"
    assert format_log_corr_suffix("bad\nid", "") == " req_id=- sub_id=-"
    assert build_validated_header("X-Test-Id", "abcdef12", _CID_RE) == {
        "X-Test-Id": "abcdef12"
    }
    assert build_validated_header("X-Test-Id", "abcdef12", _CID_RE, enabled=False) == {}
    assert build_validated_header("", "abcdef12", _CID_RE) == {}
    assert build_validated_header("X-Test-Id", "bad\r\n", _CID_RE) == {}
    assert build_validated_header("X-Test-Id", None, _CID_RE) == {}


def test_config_priority_dynamic_over_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(
        json.dumps(
            {
                "lazy_prompt_enabled": False,
                "tool_settle_eof_grace_s": 2.5,
                "corr_max_len": 32,
                "direct_mode": "direct",
                "max_prompt_bytes": 131072,
            }
        ),
        encoding="utf-8",
    )
    for k in (
        "AGY_BRIDGE_LAZY_PROMPT_ENABLED",
        "AGY_TOOL_SETTLE_EOF_GRACE_S",
        "AGY_BRIDGE_CORR_MAX_LEN",
        "AGY_BRIDGE_DIRECT_MODE",
        "AGY_BRIDGE_MAX_PROMPT_BYTES",
    ):
        monkeypatch.delenv(k, raising=False)
    assert lsc.lazy_prompt_enabled(config_path=cfg) is False
    assert lsc.tool_settle_config(config_path=cfg).eof_grace_s == 2.5
    assert lsc.corr_max_len(config_path=cfg) == 32
    assert lsc.max_prompt_bytes(config_path=cfg) == 131072
    assert lsc.apply_direct_mode_policy({}, config_path=cfg) == {"AGY_DIRECT": "1"}


def test_config_priority_env_over_dynamic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps({"lazy_prompt_enabled": False, "corr_max_len": 32}), encoding="utf-8")
    monkeypatch.setenv("AGY_BRIDGE_LAZY_PROMPT_ENABLED", "1")
    monkeypatch.setenv("AGY_TOOL_SETTLE_EOF_GRACE_S", "4.0")
    monkeypatch.setenv("AGY_BRIDGE_CORR_MAX_LEN", "999")
    monkeypatch.setenv("AGY_BRIDGE_DIRECT_MODE", "georouter")
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES", "not-an-int")
    assert lsc.lazy_prompt_enabled(config_path=cfg) is True
    assert lsc.tool_settle_config(config_path=cfg).eof_grace_s == 4.0
    assert lsc.corr_max_len(config_path=cfg) == 256
    assert lsc.max_prompt_bytes(config_path=cfg) is None
    assert lsc.apply_direct_mode_policy({"AGY_DIRECT": "1"}, config_path=cfg) == {"AGY_DIRECT": "0"}


def test_config_defaults_corrupt_json_and_loopback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "broken.json"
    bad.write_text("{broken", encoding="utf-8")
    monkeypatch.delenv("AGY_BRIDGE_DIRECT_MODE", raising=False)
    monkeypatch.delenv("AGY_BRIDGE_EXPOSE_CONV_HEADER", raising=False)
    monkeypatch.delenv("AGY_BRIDGE_MAX_PROMPT_BYTES_CAP", raising=False)
    monkeypatch.delenv("AGY_BRIDGE_QUEUE_KEEPALIVE_INTERVAL_S", raising=False)

    assert lsc.prompt_bytes_cap(config_path=bad) == 98304
    assert lsc.post_turn_anchor_enabled(config_path=bad) is True
    assert lsc.usage_drain_settings(config_path=bad) == (True, 0.5)
    assert lsc.queue_keepalive_interval_s(config_path=bad) == 15.0
    assert lsc.apply_direct_mode_policy({"AGY_DIRECT": "0"}, config_path=bad) == {
        "AGY_DIRECT": "0"
    }
    assert lsc.classify_cloud_mode({"AGY_DIRECT": "1"}) == "direct"
    assert lsc.classify_cloud_mode({"AGY_DIRECT": "0"}) == "georouter"
    assert lsc.classify_cloud_mode({}) == "georouter"

    assert lsc.is_loopback_peer(SimpleNamespace(client_address=("127.0.0.1", 5000))) is True
    assert lsc.is_loopback_peer(SimpleNamespace(client_address=("::1", 5000))) is True
    assert lsc.is_loopback_peer(SimpleNamespace(client_address=("10.0.0.5", 5000))) is False
    assert lsc.is_loopback_peer(SimpleNamespace()) is False
    assert lsc.is_loopback_peer(SimpleNamespace(client_address=())) is False

    assert lsc.build_conv_headers("abcdef12", _CID_RE, peer_is_loopback=True, config_path=bad) == {
        "X-Agy-Conversation-Id": "abcdef12"
    }
    assert lsc.build_conv_headers("abcdef12", _CID_RE, peer_is_loopback=False, config_path=bad) == {}
    monkeypatch.setenv("AGY_BRIDGE_EXPOSE_CONV_HEADER", "0")
    assert lsc.build_conv_headers("abcdef12", _CID_RE, peer_is_loopback=True, config_path=bad) == {}

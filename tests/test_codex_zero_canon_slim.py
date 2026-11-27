"""Unit & contract tests for Wave 2.2 Codex Zero-Canon prefix slimming (L1, zero I/O sockets)."""
# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from core import codex_zero_canon_slim as slim
from core.stdio_resident import codex_driver as drv
from core.stdio_resident import codex_protocol_fsm as fsm
from core.zc_admission import build_thread_params
from core.zero_canon_fs import prepare_codex_zero_canon_home


def test_slim_flag_default_on_and_falsy_kill_switch() -> None:
    assert slim.is_slim_zero_canon_enabled({}) is True
    assert slim.is_slim_zero_canon_enabled({slim.SLIM_ENABLED_ENV: "  "}) is True
    assert slim.is_slim_zero_canon_enabled({slim.SLIM_ENABLED_ENV: "1"}) is True
    for falsy in ("0", "false", "FALSE", "no", "off", " Off "):
        assert slim.is_slim_zero_canon_enabled({slim.SLIM_ENABLED_ENV: falsy}) is False


def test_resolve_base_instructions_default_override_and_omit() -> None:
    assert slim.resolve_base_instructions({}) == slim.DEFAULT_ZERO_CANON_BASE_INSTRUCTIONS
    assert slim.resolve_base_instructions({slim.SLIM_ENABLED_ENV: "0"}) is None
    assert slim.resolve_base_instructions({slim.BASE_INSTRUCTIONS_ENV: "  Custom prompt.  "}) == "Custom prompt."
    for sentinel in ("0", "false", "no", "off", "none", "NONE"):
        assert slim.resolve_base_instructions({slim.BASE_INSTRUCTIONS_ENV: sentinel}) is None


def test_resolve_disabled_features_default_custom_and_empty() -> None:
    assert slim.resolve_disabled_features({}) == slim.DEFAULT_SLIM_DISABLE_FEATURES
    assert slim.resolve_disabled_features({slim.DISABLE_FEATURES_ENV: "   "}) == slim.DEFAULT_SLIM_DISABLE_FEATURES
    assert slim.resolve_disabled_features({slim.SLIM_ENABLED_ENV: "0"}) == ()
    assert slim.resolve_disabled_features({slim.DISABLE_FEATURES_ENV: "js_repl, apps , , shell_tool"}) == (
        "js_repl",
        "apps",
        "shell_tool",
    )
    for sentinel in ("0", "false", "no", "off", "none", "disabled"):
        assert slim.resolve_disabled_features({slim.DISABLE_FEATURES_ENV: sentinel}) == ()


def test_slim_forced_config_is_immutable_and_deep_copy_prevents_aliasing() -> None:
    with pytest.raises(TypeError):
        cast(dict[str, Any], slim.SLIM_FORCED_CONFIG)["web_search"] = "live"
    nested: dict[str, Any] = {"model": "m", "nested": {"k": [1, 2]}}
    out_on = slim.apply_codex_zero_canon_slim(nested, env={})
    out_off = slim.apply_codex_zero_canon_slim(nested, env={slim.SLIM_ENABLED_ENV: "0"})
    cast(dict[str, Any], out_on["nested"])["k"].append(99)
    cast(dict[str, Any], out_off["nested"])["k"].append(88)
    assert nested["nested"]["k"] == [1, 2]


def test_apply_codex_zero_canon_slim_strips_bloat_and_preserves_proxy() -> None:
    raw: dict[str, Any] = {
        "model": "gpt-6.1-terra",
        "project_doc_max_bytes": 0,
        "agents": {"max_threads": 6, "max_depth": 2},
        "marketplaces": {"openai-bundled": {"source_type": "git"}},
        "projects": {"/Users/a/p1": {"trust_level": "trusted"}},
        "features": {"respect_system_proxy": True, "js_repl": True},
    }
    out = slim.apply_codex_zero_canon_slim(raw, env={})
    assert "marketplaces" not in out and "projects" not in out
    assert out["agents"] == {"enabled": False}
    assert out["web_search"] == "disabled"
    for key, val in slim.SLIM_FORCED_CONFIG.items():
        assert out[key] == val
    assert out["features"] == {
        "respect_system_proxy": True,
        **{feat: False for feat in slim.DEFAULT_SLIM_DISABLE_FEATURES},
    }
    # Input mapping is never mutated.
    assert "projects" in raw and cast(dict[str, Any], raw["features"])["js_repl"] is True


def test_apply_codex_zero_canon_slim_kill_switch_keeps_legacy_cfg() -> None:
    raw: dict[str, Any] = {
        "model": "gpt-6.1-terra",
        "agents": {"max_threads": 6},
        "marketplaces": {"m": {}},
        "projects": {"/p": {}},
        "features": {"respect_system_proxy": True, "js_repl": True},
    }
    out = slim.apply_codex_zero_canon_slim(raw, env={slim.SLIM_ENABLED_ENV: "0"})
    assert out == raw and out is not raw


def test_apply_codex_zero_canon_slim_omits_features_when_csv_disabled() -> None:
    out = slim.apply_codex_zero_canon_slim({"model": "m"}, env={slim.DISABLE_FEATURES_ENV: "off"})
    assert "features" not in out and out["agents"] == {"enabled": False}


def test_enrich_zero_canon_thread_params_respects_zc_flag_and_explicit_override() -> None:
    base = {"ephemeral": True, "zero_canon": True, "model": "gpt-6.1-terra"}
    enriched = slim.enrich_zero_canon_thread_params(base, True, env={})
    assert enriched["base_instructions"] == slim.DEFAULT_ZERO_CANON_BASE_INSTRUCTIONS
    assert "base_instructions" not in base

    assert "base_instructions" not in slim.enrich_zero_canon_thread_params(base, False, env={})
    assert "base_instructions" not in slim.enrich_zero_canon_thread_params(
        base, True, env={slim.SLIM_ENABLED_ENV: "0"}
    )
    explicit = {**base, "base_instructions": "Explicit"}
    assert slim.enrich_zero_canon_thread_params(explicit, True, env={})["base_instructions"] == "Explicit"
    # F-019: kill-switch and standard mode strip even pre-populated base_instructions.
    assert "base_instructions" not in slim.enrich_zero_canon_thread_params(
        explicit, True, env={slim.SLIM_ENABLED_ENV: "0"}
    )
    assert "base_instructions" not in slim.enrich_zero_canon_thread_params(explicit, False, env={})


def test_fsm_and_zc_admission_emit_base_instructions_only_in_zero_canon() -> None:
    ctx_zc = {"model": "gpt-6.1-terra", "cwd": "/tmp/zc", "base_instructions": "  Stateless.  "}
    tp_zc = build_thread_params(ctx_zc, True)
    assert tp_zc["base_instructions"] == "Stateless."
    tp_std = build_thread_params(ctx_zc, False)
    assert "base_instructions" not in tp_std

    state = fsm.ProtocolState(phase=fsm.ProtocolPhase.INITIALIZED, next_request_id=2)
    _, fx_zc = fsm.transition(state, fsm.ProtocolEvent(fsm.EventKind.START_THREAD, tp_zc))
    params_zc = cast(dict[str, Any], fx_zc[0].payload["params"])
    assert params_zc["baseInstructions"] == "Stateless."
    assert params_zc["sandbox"] == "read-only"
    assert params_zc["approvalPolicy"] == "never"

    _, fx_std = fsm.transition(
        state, fsm.ProtocolEvent(fsm.EventKind.START_THREAD, {"ephemeral": True, "zero_canon": False, "base_instructions": "Nope"})
    )
    params_std = cast(dict[str, Any], fx_std[0].payload["params"])
    assert "baseInstructions" not in params_std


def test_prepare_codex_zero_canon_home_writes_slim_config_and_honors_kill_switch(tmp_path: Path) -> None:
    src_home = tmp_path / "src_home"
    src_codex = src_home / ".codex"
    src_codex.mkdir(parents=True)
    _ = (src_codex / "auth.json").write_text('{"token":"x"}\n', encoding="utf-8")
    toml_src = "\n".join([
        'model = "gpt-6.1-terra"',
        "[agents]",
        "max_threads = 6",
        "[marketplaces.a]",
        'source = "git"',
        '[projects."/tmp/foo"]',
        'trust_level = "trusted"',
        "[features]",
        "respect_system_proxy = true",
        "js_repl = true",
        "",
    ])
    _ = (src_codex / "config.toml").write_text(toml_src, encoding="utf-8")
    base_env = {"HOME": str(src_home), "CODEX_HOME": str(src_codex)}
    out_on = prepare_codex_zero_canon_home(base_env, tmp_path / "zc-on")
    cfg_on = tomllib.loads((Path(out_on["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8"))
    assert cfg_on["project_doc_max_bytes"] == 0
    assert cfg_on["agents"] == {"enabled": False}
    assert "marketplaces" not in cfg_on and "projects" not in cfg_on
    assert cfg_on["features"]["respect_system_proxy"] is True
    assert cfg_on["features"]["js_repl"] is False and cfg_on["features"]["shell_tool"] is False
    assert cfg_on["include_permissions_instructions"] is False and cfg_on["web_search"] == "disabled"

    out_off = prepare_codex_zero_canon_home({**base_env, slim.SLIM_ENABLED_ENV: "0"}, tmp_path / "zc-off")
    cfg_off = tomllib.loads((Path(out_off["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8"))
    assert "projects" in cfg_off and "marketplaces" in cfg_off and cfg_off["features"]["js_repl"] is True


def test_codex_v2_driver_prepare_turn_sends_base_instructions_on_zero_canon(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeHandle:
        sent: list[dict[str, Any]]
        _replies: list[dict[str, Any]]

        def __init__(self) -> None:
            self.sent = []
            self._replies = [
                {"id": 1, "result": {"userAgent": "codex-cli/0.171.0"}},
                {"id": 2, "result": {"thread": {"id": "thr-real-1"}, "model": "gpt-6.1-terra"}},
            ]

        def write(self, data: bytes) -> None:
            self.sent.append(json.loads(data.decode("utf-8")))

        def read_line(self, timeout_s: float = 5.0) -> SimpleNamespace | None:
            _ = timeout_s
            if not self._replies:
                return None
            return SimpleNamespace(line=json.dumps(self._replies.pop(0)) + "\n", is_stderr=False)

    monkeypatch.delenv(slim.SLIM_ENABLED_ENV, raising=False)
    monkeypatch.delenv(slim.BASE_INSTRUCTIONS_ENV, raising=False)
    driver = drv.CodexAppServerV2Driver()
    h = _FakeHandle()
    assert driver.run_handshake(h, timeout_s=1.0) is True
    assert driver.prepare_turn(h, {"review_profile": "Zero-Canon", "model": "gpt-6.1-terra", "cwd": "/tmp/zc"}, timeout_s=1.0) is True
    thr_req = h.sent[2]
    assert thr_req["method"] == "thread/start"
    assert thr_req["params"]["baseInstructions"] == slim.DEFAULT_ZERO_CANON_BASE_INSTRUCTIONS

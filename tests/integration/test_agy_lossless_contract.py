"""L2 integration/contract tests for agy-bridge lossless prompt facade (two-profile legacy vs lossless)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGY_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(AGY_DIR) not in sys.path:
    sys.path.insert(0, str(AGY_DIR))

from agy_runtime.lossless_prompt_facade import (  # noqa: E402
    LosslessRejectionError,
    build_run_stdin_line,
    send_rejection_response,
)
from core.lossless_contracts import DEFAULT_SAFE_FRAME_BYTES  # noqa: E402


def _load_agy_server() -> ModuleType:
    name = "agy_server_lossless_test_mod"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, AGY_DIR / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_cold_hermes_messages() -> tuple[list[dict[str, str]], list[str]]:
    markers = [f"MK_{i:02d}" for i in range(1, 13)]
    block = 'Кириллица "quoted"\nline\\slash 🚀 — ' * 40
    msgs: list[dict[str, str]] = [{"role": "system", "content": "SYS " + ("S" * 83_410)}]
    for mk in markers:
        msgs.append({"role": "user", "content": f"[{mk}] " + block * 11})
        msgs.append({"role": "assistant", "content": f"ack {mk}"})
    msgs.append({"role": "user", "content": "FINAL_REQUEST_MARKER"})
    return msgs, markers


def test_two_profile_legacy_vs_lossless_300kib_cold_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_agy_server()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    msgs, markers = _make_cold_hermes_messages()

    # Profile 1: Legacy (kill-switch default False) preserves legacy truncation cap
    monkeypatch.delenv("AGY_BRIDGE_LOSSLESS_ENABLED", raising=False)
    legacy_prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)
    assert srv._ndjson_bytes(legacy_prompt) <= srv.PROMPT_MAX_NDJSON_BYTES

    # Profile 2: Lossless enabled -> zero truncation, 12/12 markers, valid <=90112B NDJSON frames
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_ENABLED", "true")
    lossless_prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)
    assert len(lossless_prompt.encode("utf-8")) > 250_000
    for mk in markers:
        assert mk in lossless_prompt
    assert "FINAL_REQUEST_MARKER" in lossless_prompt
    assert srv._ensure_prompt_fits_ndjson(lossless_prompt) == lossless_prompt

    stdin_payload = build_run_stdin_line(
        lossless_prompt,
        head_pruning_enabled=True,
        ensure_fit_fn=srv._ensure_prompt_fits_ndjson,
        ndjson_user_line_fn=srv._ndjson_user_line,
        config_path=cfg,
    )
    lines = [line for line in stdin_payload.splitlines() if line.strip()]
    assert len(lines) >= 3
    for line in lines:
        assert len((line + "\n").encode("utf-8")) <= DEFAULT_SAFE_FRAME_BYTES
    reconstructed = "".join(json.loads(line)["message"]["content"][0]["text"] for line in lines)
    assert hashlib.sha256(reconstructed.encode("utf-8")).hexdigest() == hashlib.sha256(
        lossless_prompt.encode("utf-8")
    ).hexdigest()


def test_lossless_overflow_returns_fail_closed_413_with_redacted_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_agy_server()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_ENABLED", "true")
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_MAX_CHUNKS", "2")

    secret_msgs = [{"role": "user", "content": "SECRET_TOKEN_ABC " + ("Z" * 260_000)}]
    with pytest.raises(LosslessRejectionError) as exc_info:
        srv._messages_to_prompt(secret_msgs)

    sent: list[tuple[int, dict[str, object]]] = []

    class _FakeHandler:
        def _send(self, code: int, payload: dict[str, object]) -> None:
            sent.append((code, payload))

    send_rejection_response(_FakeHandler(), exc_info.value)
    assert len(sent) == 1
    code, body = sent[0]
    assert code == 413
    wire_str = json.dumps(body)
    assert "SECRET_TOKEN_ABC" not in wire_str
    err = body["error"]
    assert isinstance(err, dict)
    assert "x_bridge_loss" in err

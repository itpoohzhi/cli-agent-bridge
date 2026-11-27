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
    feed_run_stdin_or_lossless,
    get_admission_guard,
    iter_run_stdout_or_lossless,
    prepare_run_lossless_state,
    release_run_lossless_resources,
    send_rejection_response,
)
from agy_runtime.process_admission_guard import AdmissionOverloadError, is_pgid_alive  # noqa: E402
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


def test_runtime_run_lifecycle_wires_chunk_delivery_and_admission_guard_429(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify server.py Run hooks actually invoke ProcessAdmissionGuard (429) and deliver_chunked_prompt."""
    srv = _load_agy_server()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_ENABLED", "true")
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_MAX_QUEUE", "0")
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_QUEUE_WAIT_S", "0.1")

    msgs, markers = _make_cold_hermes_messages()
    prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)
    expected_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    stub_code = (
        "import hashlib, json, sys\n"
        "parts = []\n"
        "for raw in sys.stdin:\n"
        "    if not raw.strip(): continue\n"
        "    parts.append(json.loads(raw)['message']['content'][0]['text'])\n"
        "    sha = hashlib.sha256(''.join(parts).encode('utf-8')).hexdigest()\n"
        "    sys.stdout.write(json.dumps({'type':'result','chunks':len(parts),'sha256':sha})+'\\n')\n"
        "    sys.stdout.flush()\n"
    )

    class _FakeRun:
        _stop_watch = None
        proc = None

    run1 = _FakeRun()
    _ = prepare_run_lossless_state(
        run1,
        prompt,
        head_pruning_enabled=True,
        ensure_fit_fn=srv._ensure_prompt_fits_ndjson,
        ndjson_user_line_fn=srv._ndjson_user_line,
        config_path=cfg,
    )
    assert getattr(run1, "_lossless_slot_held") is True
    assert getattr(run1, "_lossless_chunked") is True

    # While run1 holds the single slot (max_concurrency=1, max_queue=0), run2 must fail fast with 429
    run2 = _FakeRun()
    with pytest.raises(AdmissionOverloadError) as ov_exc:
        prepare_run_lossless_state(
            run2,
            "second request",
            head_pruning_enabled=True,
            ensure_fit_fn=srv._ensure_prompt_fits_ndjson,
            ndjson_user_line_fn=srv._ndjson_user_line,
            config_path=cfg,
        )
    sent_429: list[tuple[int, dict[str, object]]] = []

    class _H:
        def _send(self, code: int, payload: dict[str, object]) -> None:
            sent_429.append((code, payload))

    send_rejection_response(_H(), ov_exc.value)
    assert sent_429[0][0] == 429

    guard = get_admission_guard(cfg)
    run1.proc = guard.spawn_isolated([sys.executable, "-c", stub_code])
    pgid = run1.proc.pid
    try:
        feed_run_stdin_or_lossless(run1, lambda _r: None)
        out_lines = list(iter_run_stdout_or_lossless(run1, lambda _r: iter(())))
    finally:
        release_run_lossless_resources(run1)

    # Intermediate synthetic ACKs filtered -> exactly 1 final result event with full sha256
    assert len(out_lines) == 1
    final_ev = json.loads(out_lines[0])
    assert final_ev["chunks"] >= 4
    assert final_ev["sha256"] == expected_sha
    assert all(mk in prompt for mk in markers)
    assert not is_pgid_alive(pgid)
    assert guard.snapshot().active == 0

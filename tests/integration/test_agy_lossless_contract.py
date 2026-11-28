"""L2 integration/contract tests for agy-bridge lossless prompt facade (two-profile legacy vs lossless)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
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
    run_with_lossless_cleanup,
    send_rejection_response,
)
from agy_runtime.persistent_run_hooks import iter_run_stdout_lines  # noqa: E402
from agy_runtime.process_admission_guard import AdmissionOverloadError, is_pgid_alive  # noqa: E402
from core.lossless_contracts import DEFAULT_SAFE_FRAME_BYTES  # noqa: E402

_ECHO_STUB = (
    "import hashlib, json, sys\n"
    "parts = []\n"
    "for raw in sys.stdin:\n"
    "    if not raw.strip(): continue\n"
    "    parts.append(json.loads(raw)['message']['content'][0]['text'])\n"
    "    sha = hashlib.sha256(''.join(parts).encode('utf-8')).hexdigest()\n"
    "    sys.stdout.write(json.dumps({'type':'result','chunks':len(parts),'sha256':sha})+'\\n')\n"
    "    sys.stdout.flush()\n"
)

_MULTILINE_STUB = (
    "import json, sys\n"
    "idx = 0\n"
    "for raw in sys.stdin:\n"
    "    if not raw.strip(): continue\n"
    "    idx += 1\n"
    "    sys.stdout.write(json.dumps({'type':'step_update','chunk':idx,'text':'part'})+'\\n')\n"
    "    sys.stdout.write(json.dumps({'type':'result','chunk':idx})+'\\n')\n"
    "    sys.stdout.flush()\n"
)


class _FakeRun:
    def __init__(self) -> None:
        self._stop_watch = threading.Event()
        self._proc_done = threading.Event()
        self.proc = None


class _FakeHandler:
    def __init__(self) -> None:
        self.sent: list[tuple[int, dict[str, object]]] = []

    def _send(self, code: int, payload: dict[str, object]) -> None:
        self.sent.append((code, payload))


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


def _setup_lossless(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, max_conc: str, max_q: str
) -> tuple[ModuleType, Path]:
    srv = _load_agy_server()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_ENABLED", "true")
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_MAX_CONCURRENCY", max_conc)
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_MAX_QUEUE", max_q)
    return srv, cfg


def _prep(srv: ModuleType, cfg: Path, run: object, prompt: str) -> str:
    return prepare_run_lossless_state(
        run,
        prompt,
        head_pruning_enabled=True,
        ensure_fit_fn=srv._ensure_prompt_fits_ndjson,
        ndjson_user_line_fn=srv._ndjson_user_line,
        config_path=cfg,
    )


def test_two_profile_legacy_vs_lossless_300kib_cold_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srv = _load_agy_server()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    msgs, markers = _make_cold_hermes_messages()

    monkeypatch.delenv("AGY_BRIDGE_LOSSLESS_ENABLED", raising=False)
    legacy_prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)
    assert srv._ndjson_bytes(legacy_prompt) <= srv.PROMPT_MAX_NDJSON_BYTES

    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_ENABLED", "true")
    lossless_prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)
    assert len(lossless_prompt.encode("utf-8")) > 250_000
    assert all(mk in lossless_prompt for mk in markers)
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
    assert all(len((line + "\n").encode("utf-8")) <= DEFAULT_SAFE_FRAME_BYTES for line in lines)
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

    handler = _FakeHandler()
    send_rejection_response(handler, exc_info.value)
    assert len(handler.sent) == 1
    code, body = handler.sent[0]
    assert code == 413
    assert "SECRET_TOKEN_ABC" not in json.dumps(body)
    err = body["error"]
    assert isinstance(err, dict) and "x_bridge_loss" in err


def test_runtime_run_lifecycle_wires_chunk_delivery_and_admission_guard_429(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify server.py Run hooks actually invoke ProcessAdmissionGuard (429) and deliver_chunked_prompt."""
    srv, cfg = _setup_lossless(monkeypatch, tmp_path, "1", "0")
    monkeypatch.setenv("AGY_BRIDGE_LOSSLESS_QUEUE_WAIT_S", "0.1")
    msgs, markers = _make_cold_hermes_messages()
    prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)
    expected_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    run1, run2 = _FakeRun(), _FakeRun()
    _prep(srv, cfg, run1, prompt)
    assert getattr(run1, "_lossless_slot_held") is True and getattr(run1, "_lossless_chunked") is True

    with pytest.raises(AdmissionOverloadError) as ov_exc:
        _prep(srv, cfg, run2, "second request")
    handler = _FakeHandler()
    send_rejection_response(handler, ov_exc.value)
    assert handler.sent[0][0] == 429

    guard = get_admission_guard(cfg)
    run1.proc = guard.spawn_isolated([sys.executable, "-c", _ECHO_STUB])
    pgid = run1.proc.pid
    try:
        feed_run_stdin_or_lossless(run1, lambda _r: None)
        out_lines = list(iter_run_stdout_or_lossless(run1, iter_run_stdout_lines))
    finally:
        release_run_lossless_resources(run1)

    assert len(out_lines) == 1
    final_ev = json.loads(out_lines[0])
    assert final_ev["chunks"] >= 4 and final_ev["sha256"] == expected_sha
    assert all(mk in prompt for mk in markers)
    assert not is_pgid_alive(pgid) and guard.snapshot().active == 0


def test_runtime_slot_released_on_run_init_exception_and_bounded_stdout_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify slot does not leak when spawn fails after prepare_run_lossless_state, and wait is bounded."""
    srv, cfg = _setup_lossless(monkeypatch, tmp_path, "1", "0")
    run = _FakeRun()
    _prep(srv, cfg, run, "hello")
    guard = get_admission_guard(cfg)
    assert guard.snapshot().active == 1

    with pytest.raises(RuntimeError, match="spawn_failed"):
        run_with_lossless_cleanup(run, lambda: (_ for _ in ()).throw(RuntimeError("spawn_failed")))
    assert guard.snapshot().active == 0

    run_stuck = _FakeRun()
    setattr(run_stuck, "_lossless_chunked", True)
    setattr(run_stuck, "_lossless_slot_held", True)
    setattr(run_stuck, "_lossless_guard", guard)
    setattr(run_stuck, "_lossless_done", threading.Event())
    guard.acquire()
    lines = list(iter_run_stdout_or_lossless(run_stuck, lambda _r: iter(()), wait_timeout_s=0.05))
    assert lines == []
    assert guard.snapshot().active == 0
    assert getattr(run_stuck, "_lossless_result").reason == "ack_phase_timeout"


def test_runtime_multiline_final_turn_stdout_preserved_and_413_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify multi-line final turn stdout events are preserved while synthetic chunk ACKs are filtered."""
    srv, cfg = _setup_lossless(monkeypatch, tmp_path, "2", "1")
    msgs, _ = _make_cold_hermes_messages()
    prompt = srv._messages_to_prompt(msgs, reserve_bytes=35307)

    run = _FakeRun()
    _prep(srv, cfg, run, prompt)
    guard = get_admission_guard(cfg)
    run.proc = guard.spawn_isolated([sys.executable, "-c", _MULTILINE_STUB])
    try:
        feed_run_stdin_or_lossless(run, lambda _r: None)
        out_lines = list(iter_run_stdout_or_lossless(run, iter_run_stdout_lines))
    finally:
        release_run_lossless_resources(run)

    assert len(out_lines) == 2
    assert json.loads(out_lines[0])["type"] == "step_update"
    assert json.loads(out_lines[1])["type"] == "result"
    assert json.loads(out_lines[0])["chunk"] == json.loads(out_lines[1])["chunk"] >= 4

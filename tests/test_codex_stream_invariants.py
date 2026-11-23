"""Deterministic stream, cap, redaction, attestation, flag-off, and canary invariants (W3-C)."""

from __future__ import annotations

import hashlib
import json
import random
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import zero_canon_fs as zfs  # noqa: E402
from core import zero_canon_http as zhttp  # noqa: E402
from core.codex_zero_canon_policy import (  # noqa: E402
    ATTESTATION_HEADER,
    ERR_TOOL_EVENT_FORBIDDEN,
    ActualTurnObservation,
    CodexZeroCanonPolicyError,
    RequestedTurnSpec,
    build_attestation_receipt,
    parse_attestation_header,
)
from core.stdio_resident.config import StdioPoolConfig  # noqa: E402
from core.stdio_resident.process_io import LINE, TIMEOUT, TaggedLine  # noqa: E402
from core.stdio_resident.protocol_driver import DecodedChunk, StreamJsonDriver  # noqa: E402
from core.stdio_resident.session_manager import StdioSessionManager, TurnTimeoutError  # noqa: E402
from core.stdio_resident.sse_error_bridge import (  # noqa: E402
    SseErrorContext,
    _sanitize_log_text,
    handle_sse_stream_exception,
)
from core.stdio_resident.turn_error_sse import (  # noqa: E402
    DONE_FRAME,
    build_turn_error,
    sanitize_error_message,
)
from core.stdio_resident.turn_stream import (  # noqa: E402
    DEFAULT_AGGREGATE_OUTPUT_BYTES,
    AggregateOutputLimitError,
    StepBoundary,
    TurnStreamAssembler,
    resolve_aggregate_output_bytes,
)
from core.stdio_resident.types import SlotAffinityKey  # noqa: E402

DUMMY_KEY = "sk-dummy-test-000"
DUMMY_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJkdW1teSJ9.dummysig000"
SOL, TERRA = "gpt-6.1-sol", "gpt-6.1-terra"
V2_FLAG = "BRIDGE_CODEX_APP_SERVER_V2_ENABLED"


def _split_strategies(text: str, seed: int = 20261123) -> list[tuple[str, list[str]]]:
    rng, rand_parts, pos = random.Random(seed), list[str](), 0
    while pos < len(text):
        step = rng.randint(1, 6)
        rand_parts.append(text[pos : pos + step])
        pos += step
    return [
        ("1-chunk", [text]),
        ("1B-char", list(text)),
        ("7B-slice", [text[i : i + 7] for i in range(0, len(text), 7)]),
        ("fixed-random", rand_parts),
    ]


def test_stream_assembler_byte_exact_across_all_splits_and_step_boundary() -> None:
    """INV-01: 1/1B/7B/fixed-random splits preserve exact bytes; no spurious newlines."""
    expected = "Привет, мир! Alpha.Beta — `code_block` [1/2] PONG 🚀\nLine2.Next"
    for label, parts in _split_strategies(expected):
        ticks = 0
        asm = TurnStreamAssembler(lambda: None, aggregate_output_bytes=4096)
        out: list[str] = []
        for part in parts:
            delta = asm.process_chunk(DecodedChunk(text=part))
            out.append(delta.content)
            ticks += 1
        assert "".join(out) == expected, f"split drift for {label}"
        assert ticks == len(parts) and asm.aggregate_bytes == len(expected.encode("utf-8"))

    stepped = TurnStreamAssembler(aggregate_output_bytes=256)
    p1 = stepped.process_chunk(DecodedChunk(text="Step one.")).content
    _ = stepped.process_chunk(StepBoundary())
    p2 = stepped.process_chunk(DecodedChunk(text="Step two.")).content
    p3 = stepped.process_chunk(DecodedChunk(text="Step three.", raw={"step_boundary": True})).content
    assert p1 + p2 + p3 == "Step one.\n\nStep two.\n\nStep three."

    isolated = TurnStreamAssembler(aggregate_output_bytes=256)
    _ = isolated.process_chunk(DecodedChunk(tool_calls=[{"id": "c1", "function": {"name": "x"}}]))
    post = isolated.process_chunk(DecodedChunk(text="internal note"))
    assert post.content == "" and post.reasoning_content == "internal note"


def test_aggregate_output_cap_utf8_boundaries_and_config_precedence(tmp_path: Path) -> None:
    """INV-02: UTF-8 byte cap counts content+reasoning+tools; dynamic_config > env > default."""
    payload = "Ж" * 3  # 6 UTF-8 bytes
    exact = TurnStreamAssembler(aggregate_output_bytes=6)
    assert exact.process_chunk(DecodedChunk(text=payload)).content == payload
    assert exact.aggregate_bytes == 6

    with pytest.raises(AggregateOutputLimitError, match="output_limit_exceeded") as exc_info:
        _ = exact.process_chunk(DecodedChunk(reasoning="a"))
    assert (exc_info.value.code, exc_info.value.http_status, exc_info.value.limit_bytes) == ("output_limit_exceeded", 502, 6)

    tool_capped = TurnStreamAssembler(aggregate_output_bytes=12)
    with pytest.raises(AggregateOutputLimitError, match="output_limit_exceeded"):
        _ = tool_capped.process_chunk(DecodedChunk(tool_calls=[{"id": "call-1", "name": "huge_tool"}]))

    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps({"BRIDGE_STDIO_AGGREGATE_OUTPUT_BYTES": 2048}), encoding="utf-8")
    env = {"BRIDGE_DYNAMIC_CONFIG_PATH": str(cfg), "BRIDGE_STDIO_AGGREGATE_OUTPUT_BYTES": "4096"}
    assert resolve_aggregate_output_bytes(env) == 2048
    cfg.write_text("{broken", encoding="utf-8")
    assert resolve_aggregate_output_bytes(env) == 4096
    assert resolve_aggregate_output_bytes({"BRIDGE_DYNAMIC_CONFIG_PATH": str(cfg)}) == DEFAULT_AGGREGATE_OUTPUT_BYTES


class _ClockHandle:
    """Fake stdio handle driven by a monotonic fake clock (zero sleeps, zero sockets)."""

    def __init__(self, script: list[tuple[float, str, str | None]], clock: list[float]) -> None:
        self._script, self._clock = list(script), clock
        self.pid, self.generation, self._pgid_dead = 7001, 0, True

    def write(self, data: bytes) -> None:
        _ = data

    def read_line_outcome(self, timeout_s: float | None = None) -> tuple[str, TaggedLine | None]:
        _ = timeout_s
        dt, kind, line = self._script.pop(0)
        self._clock[0] += dt
        if kind == LINE and line is not None:
            return (LINE, TaggedLine(line=line, generation=0, pid=self.pid, is_stderr=False))
        return (kind, None)


class _ClockPool:
    def __init__(self, handle: _ClockHandle) -> None:
        self._handle = handle
        self.releases: list[tuple[bool, bool]] = []

    def acquire(self, key: SlotAffinityKey, *_: Any, **__: Any) -> Any:
        return SimpleNamespace(slot_id="s1", handle=self._handle, affinity_key=key, lease_id="l1")

    def release(self, _slot_id: str, *, success: bool = False, cancel: bool = False, **__: Any) -> None:
        self.releases.append((success, cancel))


def test_sliding_activity_window_fake_clock_extends_idle_and_honors_safety_cap() -> None:
    """INV-03: Useful deltas extend idle deadline beyond static idle_s; safety_cap still fires."""
    clock = [100.0]
    ev = json.dumps({"type": "text", "text": "tick"})
    done = json.dumps({"type": "done", "text": "done"})
    handle = _ClockHandle([(8.0, LINE, ev), (8.0, LINE, ev), (8.0, LINE, done)], clock)
    cfg = StdioPoolConfig(turn_total_timeout_s=30.0)
    mgr = StdioSessionManager(_ClockPool(handle), StreamJsonDriver(), cfg, clock=lambda: clock[0])  # type: ignore[arg-type]
    key = SlotAffinityKey("own", "c1", "codex", SOL, "high", "/tmp", "standard")
    ctx = {"first_progress_timeout_s": 10.0, "idle_timeout_s": 10.0, "safety_cap_s": 30.0}
    res = mgr.execute_turn(key, "hi", lambda: ["fake"], "/tmp", turn_context=ctx)
    assert len(res.chunks) == 3 and clock[0] == 124.0

    clock2 = [200.0]
    cap_handle = _ClockHandle([(12.0, LINE, ev), (20.0, TIMEOUT, None)], clock2)
    mgr2 = StdioSessionManager(_ClockPool(cap_handle), StreamJsonDriver(), cfg, clock=lambda: clock2[0])  # type: ignore[arg-type]
    with pytest.raises(TurnTimeoutError, match="safety_cap_timeout") as err:
        _ = mgr2.execute_turn(key, "hi", lambda: ["fake"], "/tmp", turn_context={"first_progress_timeout_s": 15.0, "idle_timeout_s": 25.0, "safety_cap_s": 30.0})
    assert err.value.timeout_kind == "safety_cap"


def test_redaction_before_truncation_and_sse_error_bridge_invariants() -> None:
    """INV-04: Secrets redacted before truncation; error codes preserved; mid-stream never stops."""
    raw = f"{ERR_TOOL_EVENT_FORBIDDEN} auth Bearer {DUMMY_KEY} apiKey={DUMMY_KEY} jwt={DUMMY_JWT}"
    short = sanitize_error_message(raw, max_chars=52)
    log_line = _sanitize_log_text(raw, extra_code=ERR_TOOL_EVENT_FORBIDDEN, max_chars=52)
    for text in (short, log_line):
        assert ERR_TOOL_EVENT_FORBIDDEN in text
        assert DUMMY_KEY not in text and "sk-dummy" not in text and DUMMY_JWT not in text

    pre = build_turn_error(RuntimeError(raw), live_sent=0, max_chars=60)
    mid = build_turn_error(RuntimeError(raw), live_sent=1, max_chars=60)
    assert (pre.status, mid.status, pre.code) == (502, 200, ERR_TOOL_EVENT_FORBIDDEN)
    for blob in (pre.sse, mid.sse, json.dumps(pre.body)):
        assert DUMMY_KEY not in blob and DUMMY_JWT not in blob

    emitted, logs = list[str](), list[str]()
    lease = SimpleNamespace(failures=[], discards=[], record_failure=lambda e: lease.failures.append(e), record_discard=lambda r: lease.discards.append(r))
    handler = SimpleNamespace(_headers_already_sent=True, _client_write_dead=False, _response_status=200)
    ctx = SseErrorContext(handler, lease, lambda f: (emitted.append(f), True)[1], lambda m, **kw: json.dumps({"msg": m, **kw}), logs.append)
    assert handle_sse_stream_exception(RuntimeError(raw), 5, ctx) is True
    frame = json.loads(emitted[0])
    assert frame["code"] == ERR_TOOL_EVENT_FORBIDDEN and frame["finish_reason"] is None and emitted[-1] == DONE_FRAME
    assert DUMMY_KEY not in emitted[0] and all(DUMMY_KEY not in entry for entry in logs)


def test_two_phase_attestation_header_projection_and_flag_off_503(tmp_path: Path) -> None:
    """INV-05: Two-phase admitted/completed proofs, spoof stripping, and V2 flag-off 503."""
    adm = zhttp.ZeroCanonAdmissionProof(TERRA, "medium", "thr-srv-9", "trn-srv-9", clean_home_verified=True, handshake_acked=True, requested_model=TERRA, requested_effort="medium")
    h_adm = zhttp.build_attestation_header(adm, phase="admitted")
    h_cmp = zhttp.build_attestation_header(zhttp.ZeroCanonCompletionProof(adm, terminal_status="completed"), phase="completed")
    assert parse_attestation_header(h_adm)["phase"] == "admitted"
    assert parse_attestation_header(h_cmp)["phase"] == "completed"

    with pytest.raises(zhttp.ZeroCanonHttpError, match="zero_canon_attestation_failed"):
        _ = zhttp.build_attestation_header(adm, phase="completed")
    with pytest.raises(zhttp.ZeroCanonHttpError, match="zero_canon_attestation_failed"):
        _ = zhttp.build_attestation_header(zhttp.ZeroCanonCompletionProof(adm, terminal_status="completed", tool_events_seen=1), phase="completed")
    with pytest.raises(CodexZeroCanonPolicyError, match="Identity mismatch"):
        _ = build_attestation_receipt(RequestedTurnSpec(SOL, "xhigh"), ActualTurnObservation(SOL, "high", terminal_status="completed"), phase="completed")

    sent: list[tuple[str, str]] = []
    fake_h = SimpleNamespace(
        _zero_canon_admission=adm, _zero_canon_completion=None,
        send_header=lambda k, v: sent.append((k, v)), end_headers=lambda: None,
    )
    zhttp.emit_turn_headers(fake_h, None, [(ATTESTATION_HEADER, "spoof"), ("X-Trace", "1")], ("", None), attestation=(adm, "admitted"))
    assert fake_h._zero_canon_admission is None
    assert [k for k, _ in sent] == ["X-Trace", ATTESTATION_HEADER] and "spoof" not in sent[1][1]

    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps({V2_FLAG: False}), encoding="utf-8")
    assert zhttp.is_codex_app_server_v2_enabled({V2_FLAG: "true"}, config_path=cfg) is False
    routes = [
        {"route_id": "openai-key-3", "backend": "openai-key-3", "base_url": "https://api.example.invalid/v1"},
        {"route_id": "codex-app-server-v2", "backend": "codex", "kind": "stdio_resident"},
    ]
    with pytest.raises(zhttp.ZeroCanonHttpError, match="zero_canon_unsupported_by_driver") as err503:
        _ = zhttp.filter_zero_canon_providers(routes, "Zero-Canon", codex_v2_enabled=False, model_id=SOL)
    assert err503.value.status_code == 503


def test_zero_canon_fs_canary_nofollow_and_atomic_0600(tmp_path: Path) -> None:
    """INV-06: Clean-home isolates env/config with 0o700/0o600, rejects symlinks, preserves canary."""
    home = tmp_path / "canary_home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True, mode=0o700)
    cfg = codex_dir / "config.toml"
    auth = codex_dir / "auth.json"
    cfg.write_text('model = "gpt-6.1-terra"\n[plugins.bad]\nenabled = true\n[hooks]\non_turn = "x"\n', encoding="utf-8")
    auth.write_text(json.dumps({"OPENAI_API_KEY": DUMMY_KEY}), encoding="utf-8")
    h_cfg = hashlib.sha256(cfg.read_bytes()).hexdigest()
    h_auth = hashlib.sha256(auth.read_bytes()).hexdigest()

    env = zfs.prepare_codex_zero_canon_home({"HOME": str(home), "CODEX_HOME": str(codex_dir), "BRIDGE_KEY": DUMMY_KEY}, tmp_path / "zc-inv")
    dst = Path(env["CODEX_HOME"])
    assert stat.S_IMODE(dst.stat().st_mode) == 0o700 and stat.S_IMODE((dst / "auth.json").stat().st_mode) == 0o600
    assert "BRIDGE_KEY" not in env and "hooks" not in (dst / "config.toml").read_text(encoding="utf-8")
    assert "project_doc_max_bytes = 0" in (dst / "config.toml").read_text(encoding="utf-8")
    assert hashlib.sha256(cfg.read_bytes()).hexdigest() == h_cfg and hashlib.sha256(auth.read_bytes()).hexdigest() == h_auth

    sym = tmp_path / "sym_auth.json"
    sym.symlink_to(auth)
    with pytest.raises(OSError):
        _ = zfs.read_regular_file_nofollow(sym)
    with pytest.raises(OSError):
        zfs.write_atomic_0600(sym, b"overwrite")
    with pytest.raises(FileExistsError):
        zfs.write_atomic_0600(auth, b"overwrite")
    assert hashlib.sha256(auth.read_bytes()).hexdigest() == h_auth

"""W3-B Live-Isolated route E2E (VER-026): stub agy -> agy-bridge -> hub passthrough.

Изолированный маршрут на эфемерных loopback-портах (`live_isolated_harness`, стаб
`tests/agy_stub_agent.py`, HOME=<tmp>, отдельный PGID): usage.x_bridge_loss остаётся
байт-в-байт идентичным для non-stream и stream при modified=false/true, тело 400
client_compaction_required релеится без изменений. Wire-capture пишется в
`.ai-team/runs/agy-bridge-hermes-truncation-fix-20261127/qa/wire-capture.json`.
"""

from __future__ import annotations

import http.client
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from adapters.passthrough_adapter import PassthroughAdapter, PassthroughLimits  # noqa: E402
from core.passthrough_stream_options import prepare_stream_usage_body  # noqa: E402
from live_isolated_harness import ALL_ON, API_KEY, MODEL, running  # noqa: E402

QA_PATH: Final = (
    ROOT / ".ai-team" / "runs" / "agy-bridge-hermes-truncation-fix-20261127"
    / "qa" / "wire-capture.json"
)
CAP_ENV: Final = {"AGY_BRIDGE_MAX_PROMPT_BYTES": "16384", "AGY_HISTORY_COMPACTION_ENABLED": "1"}
HubFacts = dict[str, Any]


@pytest.fixture(autouse=True)
def _hub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Детерминированный хаб-хоп: retry/early-flush выключены, инъекция usage включена."""
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_STREAM_PRECOMMIT_FLUSH_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_STREAM_PASSTHROUGH_EARLY_FLUSH_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_STREAM_USAGE_ENABLED", "true")


@pytest.fixture(scope="module")
def capture() -> Iterator[HubFacts]:
    """Накопитель wire-capture: каждый тест долиет свои факты и перезапишет JSON."""
    facts: HubFacts = {"schema_version": "wire-capture/v1", "cases": {}}
    yield facts
    _flush(facts)


def _flush(facts: HubFacts) -> None:
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    QA_PATH.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")


def _record(facts: HubFacts, case: str, entry: HubFacts) -> None:
    facts["cases"][case] = entry
    _flush(facts)


def _extra(tmp_path: Path) -> dict[str, str]:
    """PYTHONPATH ведёт в копию repo изолированного контура, не в живой репозиторий."""
    return {**CAP_ENV, "PYTHONPATH": str(tmp_path / "repo")}


def _post(port: int, body: dict[str, Any]) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=90)
    try:
        conn.request(
            "POST", "/v1/chat/completions", json.dumps(body),
            {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


class _Sink:
    """Захват wire-байтов ответа хаба (единственный писатель, без сети клиенту)."""

    accepts_presend_errors = False

    def __init__(self) -> None:
        self.status, self.chunks = 0, []

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.status = status

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    def client_gone(self) -> bool:
        return False

    def error_type(self) -> str:
        return ""

    @property
    def raw(self) -> bytes:
        return b"".join(self.chunks)


def _hop(port: int, body: dict[str, Any], sanitize: bool) -> _Sink:
    """Реальный PassthroughAdapter хаба против живого моста на loopback :0."""
    adapter = PassthroughAdapter(
        "agy", {"base_url": f"http://127.0.0.1:{port}/v1", "api_key": API_KEY},
        lambda: {}, sanitize=sanitize,
        limits=PassthroughLimits(read_timeout_s=30, idle_timeout_s=60, total_timeout_s=90),
    )
    sink = _Sink()
    try:
        adapter.handle(
            path="/v1/chat/completions", raw_body=json.dumps(body).encode(),
            request=body, headers={}, sink=sink,
        )
    finally:
        adapter.shutdown()
    return sink


def _history(n: int = 30) -> list[dict[str, str]]:
    msgs = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i} " + "x" * 1400}
        for i in range(n)
    ]
    return [*msgs, {"role": "user", "content": "final question"}]


def _usage_frames(raw: bytes) -> list[bytes]:
    return [ln for ln in raw.splitlines() if ln.startswith(b"data: {") and b'"usage"' in ln]


def _raw_loss(raw: bytes) -> bytes:
    """Сырые байты объекта x_bridge_loss из wire (баланс скобок), без переупаковки."""
    start = raw.find(b'"x_bridge_loss":')
    if start < 0:
        return b""
    begin = raw.find(b"{", start)
    depth = 0
    for pos in range(begin, len(raw)):
        if raw[pos:pos + 1] == b"{":
            depth += 1
        elif raw[pos:pos + 1] == b"}":
            depth -= 1
            if depth == 0:
                return raw[begin:pos + 1]
    return b""


def _loss(usage: object) -> object:
    return usage.get("x_bridge_loss") if isinstance(usage, dict) else None


def _canon(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def test_nonstream_receipt_byte_identical_through_hub(
    tmp_path: Path, capture: HubFacts
) -> None:
    with running(tmp_path, "eof_then_ok", dict(ALL_ON), _extra(tmp_path)) as bridge:
        bridge.chat(tools=False)  # спавн 0 стаба — EOF; дальше успешные спавны
        body = {"model": MODEL, "stream": False, "messages": _history()}
        status, raw = _post(bridge.port, body)
        sink = _hop(bridge.port, body, sanitize=True)
        leaks = bridge.leaks
    direct = json.loads(raw).get("usage")
    hubbed = json.loads(sink.raw).get("usage")
    assert status == 200 and sink.status == 200
    receipt = _loss(direct)
    assert isinstance(receipt, dict) and receipt["truncated"] is True
    assert receipt["original_messages"] == 31
    assert receipt["effective_messages"] + receipt["digested_messages"] + receipt["dropped_messages"] == 31
    assert _canon(_loss(hubbed)) == _canon(receipt)
    assert _raw_loss(sink.raw) == _raw_loss(raw) != b""  # байт-в-байт после passthrough
    assert bridge.is_clean, leaks
    _record(capture, "nonstream_truncated", {
        "status": status, "hub_status": sink.status,
        "loss_byte_identical": _raw_loss(sink.raw) == _raw_loss(raw),
        "x_bridge_loss": receipt,
    })


@pytest.mark.parametrize("modified", [False, True])
def test_stream_receipt_byte_identical_modified_false_and_true(
    tmp_path: Path, capture: HubFacts, modified: bool
) -> None:
    """modified=false: клиентский include_usage не перезаписывается; true: хаб инъектит."""
    with running(tmp_path, "eof_then_ok", dict(ALL_ON), _extra(tmp_path)) as bridge:
        bridge.chat(tools=False)
        body = {"model": MODEL, "stream": True, "messages": _history()}
        if not modified:
            body["stream_options"] = {"include_usage": True}
        _, injected = prepare_stream_usage_body(
            "/v1/chat/completions", body, json.dumps(body).encode(),
            enabled=True, supports=True, negative_hit=False,
        )
        assert injected is modified
        status, raw = _post(bridge.port, body)
        frames = _usage_frames(raw)
        hops = [_hop(bridge.port, body, sanitize=s) for s in (False, True)]
        leaks = bridge.leaks
    assert status == 200 and len(frames) == 1 and raw.count(b"data: [DONE]") == 1
    for sink in hops:
        assert sink.status == 200 and sink.raw.count(b"data: [DONE]") == 1
        assert b'"error"' not in sink.raw
        hop_frames = _usage_frames(sink.raw)
        assert len(hop_frames) == 1
        assert _raw_loss(hop_frames[0]) == _raw_loss(frames[0]) != b""
    receipt = json.loads(frames[0][6:])["usage"]["x_bridge_loss"]
    assert receipt["truncated"] is True and receipt["schema_version"] == "loss-receipt/v1"
    assert bridge.is_clean, leaks
    _record(capture, f"stream_modified_{modified}", {
        "status": status, "injected_by_hub": injected,
        "usage_frame": frames[0].decode("utf-8"),
        "sanitize_false_loss_byte_identical": _raw_loss(_usage_frames(hops[0].raw)[0]) == _raw_loss(frames[0]),
        "sanitize_true_loss_byte_identical": _raw_loss(_usage_frames(hops[1].raw)[0]) == _raw_loss(frames[0]),
    })


def test_lossless_route_claims_no_loss(tmp_path: Path, capture: HubFacts) -> None:
    """AD-007: lossless не заявляет потерь; подавленный stream usage остаётся отсутствующим."""
    with running(tmp_path, "eof_then_ok", dict(ALL_ON), _extra(tmp_path)) as bridge:
        bridge.chat(tools=False)
        body = {"model": MODEL, "stream": False, "messages": [{"role": "user", "content": "hi"}]}
        status, raw = _post(bridge.port, body)
        sink = _hop(bridge.port, body, sanitize=True)
        sbody = {**body, "stream": True}
        sstatus, sraw = _post(bridge.port, sbody)
        ssink = _hop(bridge.port, sbody, sanitize=True)
        leaks = bridge.leaks
    assert status == 200 and sink.status == 200 and sstatus == 200 and ssink.status == 200
    receipt = _loss(json.loads(raw).get("usage"))
    assert receipt is None or receipt["truncated"] is False
    assert _raw_loss(sink.raw) == _raw_loss(raw)
    assert _usage_frames(sraw) == [] and _usage_frames(ssink.raw) == []
    assert bridge.is_clean, leaks
    _record(capture, "lossless", {
        "status": status, "hub_status": sink.status,
        "truncated": False, "stream_usage_absent": True,
    })


def test_400_client_compaction_required_relayed_byte_identical(
    tmp_path: Path, capture: HubFacts
) -> None:
    with running(tmp_path, "eof_then_ok", dict(ALL_ON), _extra(tmp_path)) as bridge:
        bridge.chat(tools=False)
        body = {"model": MODEL, "stream": False,
                "messages": [{"role": "user", "content": "y" * (5 * 1024 * 1024)}]}
        status, raw = _post(bridge.port, body)
        sink = _hop(bridge.port, body, sanitize=True)
        leaks = bridge.leaks
    assert status == 400 and sink.status == 400 and sink.raw == raw
    error = json.loads(raw)["error"]
    assert error["type"] == "invalid_request_error"
    assert error["code"] == "context_length_exceeded" and error["param"] == "messages"
    assert error["x_reason"] == "client_compaction_required"
    receipt = error["x_bridge_loss"]
    assert receipt["truncated"] is True and receipt["fallback_reason"] == "input_guard"
    assert "compact the conversation and retry" in error["message"]
    assert bridge.is_clean, leaks
    _record(capture, "reject_400", {
        "status": status, "hub_status": sink.status, "raw_byte_identical": sink.raw == raw,
        "body": error,
    })


def test_wire_capture_covers_all_route_cases(capture: HubFacts) -> None:
    """Финальный read-back: wire-capture.json содержит все кейсы маршрута."""
    _flush(capture)
    data = json.loads(QA_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    for key in ("nonstream_truncated", "stream_modified_False", "stream_modified_True",
                "lossless", "reject_400"):
        assert key in cases, f"wire-capture missing {key}"
    assert cases["nonstream_truncated"]["loss_byte_identical"] is True
    assert cases["reject_400"]["raw_byte_identical"] is True

"""P0-2 (живой SSE-стриминг :9882 -> :9881) и P0-3 (stderr drain без 2x time.sleep) регрессии."""

from __future__ import annotations

# pyright: reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnusedCallResult=false, reportPrivateUsage=false

import ast
import importlib.util
import io
import json
import queue
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.stdio_resident import routed_turn_result as rtr
from core.stdio_resident.bridge_proxy_payload import build_bridge_proxy_body
from core.stdio_resident.routed_turn_result import RoutedExecOptions, RoutedTurnResult
from core.stdio_resident.zero_canon_router import (
    proxy_zero_canon_bridge_turn_result as proxy_turn_result,
)
from core.turn_usage import TurnUsage

_ROOT = Path(__file__).resolve().parents[1]
_SSE_PATH = _ROOT / "core" / "stdio_resident" / "bridge_proxy_sse.py"
_SERVER_PATH = _ROOT / "bridges" / "claude-p-bridge" / "server.py"
_URL = "http://127.0.0.1:9881/v1"
_USAGE: dict[str, Any] = {
    "prompt_tokens": 10,
    "completion_tokens": 2,
    "total_tokens": 12,
    "prompt_tokens_details": {"cached_tokens": 4},
    "completion_tokens_details": {"reasoning_tokens": 1},
}
_EXPECTED_USAGE = TurnUsage(10, 2, 4, None, 1, "claude_zero_canon_bridge")


class _JsonResp(io.BytesIO):
    def __init__(self, payload: bytes, content_type: str = "application/json") -> None:
        super().__init__(payload)
        self.headers = {"Content-Type": content_type}


class _GatedSseResp:
    """1-й чанк сразу, 2-й — только после `gate`: доказательство живого стриминга, а не read()."""

    def __init__(self, first: bytes, second: bytes, gate: threading.Event) -> None:
        self.headers = {"Content-Type": "text/event-stream"}
        self.first_read = threading.Event()
        self.sizes: list[int] = []
        self._chunks = [first, second]
        self._gate = gate

    def __enter__(self) -> "_GatedSseResp":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            raise AssertionError("bulk resp.read() buffers whole stream (P0-2 regression)")
        return self.read1(size)

    def read1(self, size: int = -1) -> bytes:
        self.sizes.append(size)
        if not self._chunks:
            return b""
        if len(self._chunks) == 1:
            self.first_read.set()
            if not self._gate.wait(10.0):
                raise AssertionError("gate timeout")
        return self._chunks.pop(0)


class _Opener:
    def __init__(self, resp: Any, requests: list[Any]) -> None:
        self._resp = resp
        self._requests = requests

    def open(self, req: Any, timeout: float = 10.0) -> Any:
        _ = timeout
        self._requests.append(req)
        return self._resp


def _bridge_route() -> Any:
    return SimpleNamespace(kind="bridge", base_url=_URL, is_ephemeral=False)


def test_p0_2_body_stream_default_is_backward_compatible() -> None:
    assert build_bridge_proxy_body("m", "p")["stream"] is False
    assert build_bridge_proxy_body("m", "p", None, stream=True)["stream"] is True


def test_p0_2_stream_body_forces_terminal_usage() -> None:
    body = build_bridge_proxy_body("m", "p", stream=True)
    assert body["stream_options"] == {"include_usage": True}
    assert "stream_options" not in build_bridge_proxy_body("m", "p", stream=False)


def test_p0_2_chunk_bytes_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_CHUNK_BYTES", "17")
    assert rtr.bridge_stream_chunk_bytes() == 17
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_CHUNK_BYTES", "oops")
    assert rtr.bridge_stream_chunk_bytes() == 4096
    monkeypatch.delenv("BRIDGE_ZC_CLAUDE_STREAM_CHUNK_BYTES", raising=False)
    assert rtr.bridge_stream_chunk_bytes() == 4096


def test_p0_2_first_chunk_reaches_writer_before_second_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    monkeypatch.delenv("BRIDGE_ZC_CLAUDE_STREAM_CHUNK_BYTES", raising=False)
    first = b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
    second = (
        'data: {"choices":[{"delta":{"content":" world"}}],"usage":'
        + json.dumps(_USAGE)
        + "}\n\ndata: [DONE]\n\n"
    ).encode("utf-8")
    gate = threading.Event()
    resp = _GatedSseResp(first, second, gate)
    requests: list[Any] = []
    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _Opener(resp, requests))
    seen: list[tuple[str, str]] = []
    got_first = threading.Event()

    def writer(kind: str, value: str) -> None:
        seen.append((kind, value))
        got_first.set()

    box: dict[str, Any] = {}

    def run() -> None:
        box["res"] = proxy_turn_result(_URL, "claude-sonnet", "ping", sse_writer=writer)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        assert got_first.wait(10.0), "TTFT: первый SSE-чанк не дошёл до sse_writer"
        assert resp.first_read.is_set()
        assert not gate.is_set(), "первый чанк обязан прийти до разблокировки второго"
        assert seen == [("content", "Hello")]
    finally:
        gate.set()
    worker.join(10.0)
    assert not worker.is_alive()
    res = box["res"]
    assert res.text == "Hello world"
    assert res.usage == _EXPECTED_USAGE
    assert seen == [("content", "Hello"), ("content", " world")]
    assert resp.sizes and all(s == 4096 for s in resp.sizes)
    assert json.loads(requests[0].data.decode("utf-8"))["stream"] is True


def test_p0_2_bridge_error_frame_is_not_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = 'data: {"error":{"message":"upstream failed","type":"proxy_error","code":"E1"},"choices":[{"delta":{"content":"\\n\\n[⚠️ Ошибка шлюза: upstream failed]"}}]}\n\ndata: [DONE]\n\n'.encode("utf-8")
    requests: list[Any] = []
    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _Opener(_JsonResp(payload, "text/event-stream"), requests))
    seen: list[tuple[str, str]] = []
    with pytest.raises(rtr.ResidentTurnError) as exc_info:
        rtr.execute_routed_turn_result(lambda _req: iter([]), _bridge_route(), {"prompt": "p"}, lambda k, v: seen.append((k, v)), RoutedExecOptions(bridge_proxy_fn=proxy_turn_result))
    assert exc_info.value.response.status == 502
    assert all("[⚠️ Ошибка шлюза" not in value for _, value in seen)


def test_p0_2_bridge_error_after_chunk_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: {"error":{"message":"upstream failed"},"choices":[{"delta":{"content":"\\n\\n[⚠️ Ошибка шлюза: upstream failed]"}}]}\n\n'.encode("utf-8")
    requests: list[Any] = []
    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _Opener(_JsonResp(payload, "text/event-stream"), requests))
    seen: list[tuple[str, str]] = []
    with pytest.raises(rtr.ResidentTurnError) as exc_info:
        rtr.execute_routed_turn_result(lambda _req: iter([]), _bridge_route(), {"prompt": "p"}, lambda k, v: seen.append((k, v)), RoutedExecOptions(bridge_proxy_fn=proxy_turn_result))
    assert exc_info.value.response.status == 200
    assert all("[⚠️ Ошибка шлюза" not in value for _, value in seen)


def test_p0_2_streamed_tool_calls_merge_fragments_by_index(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = (
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"read_file","arguments":""}}]}}]}\n\n'
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"path\\":\\""}}]}}]}\n\n'
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"a.py\\"}"}}]}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    requests: list[Any] = []
    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *_a: _Opener(_JsonResp(payload, "text/event-stream"), requests),
    )
    res = proxy_turn_result(_URL, "claude-sonnet", "ping", sse_writer=lambda _k, _v: None)
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0]["id"] == "call_1"
    assert res.tool_calls[0]["function"]["name"] == "read_file"
    assert json.loads(res.tool_calls[0]["function"]["arguments"]) == {"path": "a.py"}


def test_p0_2_writer_error_on_first_delta_keeps_live_sent_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
    requests: list[Any] = []
    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *_a: _Opener(_JsonResp(payload, "text/event-stream"), requests),
    )

    def broken_writer(_k: str, _v: str) -> None:
        raise BrokenPipeError("client disconnected")

    with pytest.raises(rtr.ResidentTurnError) as exc_info:
        rtr.execute_routed_turn_result(
            lambda _req: iter([]),
            _bridge_route(),
            {"prompt": "p"},
            broken_writer,
            RoutedExecOptions(bridge_proxy_fn=proxy_turn_result),
        )
    assert exc_info.value.response.status == 502


def test_p0_2_route_does_not_duplicate_streamed_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = (
        b'data: {"choices":[{"delta":{"reasoning_content":"think"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"ans"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    requests: list[Any] = []
    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *_a: _Opener(_JsonResp(payload, "text/event-stream"), requests),
    )
    seen: list[tuple[str, str]] = []
    res = rtr.execute_routed_turn_result(
        lambda _req: iter([]),
        _bridge_route(),
        {"prompt": "ping", "model": "claude-sonnet"},
        lambda k, v: seen.append((k, v)),
        RoutedExecOptions(bridge_proxy_fn=proxy_turn_result),
    )
    assert res.text == "ans" and res.reasoning == "think"
    assert seen == [("reasoning_content", "think"), ("content", "ans")]


def test_p0_2_legacy_bridge_proxy_fn_without_sse_writer_still_emits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")

    def legacy(
        base_url: str, model: str, prompt: str, headers: Any = None, *, usage_enabled: bool = True
    ) -> RoutedTurnResult:
        _ = (base_url, model, prompt, headers, usage_enabled)
        return RoutedTurnResult("hi", "r", None)

    seen: list[tuple[str, str]] = []
    res = rtr.execute_routed_turn_result(
        lambda _req: iter([]),
        _bridge_route(),
        {"prompt": "p"},
        lambda k, v: seen.append((k, v)),
        RoutedExecOptions(bridge_proxy_fn=legacy),
    )
    assert res.text == "hi" and res.reasoning == "r"
    assert seen == [("content", "hi"), ("reasoning_content", "r")]


@pytest.mark.parametrize("flag", ["0", "false", "off"])
def test_p0_2_kill_switch_forces_stream_false(monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", flag)
    payload = json.dumps(
        {"choices": [{"message": {"content": "hi", "reasoning_content": "r"}}], "usage": _USAGE}
    ).encode("utf-8")
    requests: list[Any] = []
    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _Opener(_JsonResp(payload), requests))
    seen: list[tuple[str, str]] = []
    res = proxy_turn_result(_URL, "claude-sonnet", "ping", sse_writer=lambda k, v: seen.append((k, v)))
    assert json.loads(requests[0].data.decode("utf-8"))["stream"] is False
    assert res.text == "hi" and res.reasoning == "r"
    assert res.usage == _EXPECTED_USAGE
    assert seen == [("content", "hi"), ("reasoning_content", "r")]


def test_p0_2_non_sse_json_fallback_emits_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = json.dumps(
        {"choices": [{"message": {"content": "hi", "reasoning_content": "r"}}], "usage": _USAGE}
    ).encode("utf-8")
    requests: list[Any] = []
    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _Opener(_JsonResp(payload), requests))
    seen: list[tuple[str, str]] = []
    res = proxy_turn_result(_URL, "claude-sonnet", "ping", sse_writer=lambda k, v: seen.append((k, v)))
    assert json.loads(requests[0].data.decode("utf-8"))["stream"] is True
    assert res.text == "hi" and res.usage == _EXPECTED_USAGE
    assert seen == [("content", "hi"), ("reasoning_content", "r")]


def _sse_frames() -> bytes:
    usage = {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    frames = [
        ": ping\r\n\r\n",
        "event: message\n",
        "data: "
        + json.dumps({"choices": [{"delta": {"reasoning_content": "Думаю 🚀"}}]}, ensure_ascii=False)
        + "\r\n\r\n",
        "data: "
        + json.dumps({"choices": [{"delta": {"content": 'Привет, "мир" 🚀'}}]}, ensure_ascii=False)
        + "\n\n",
        "data: "
        + json.dumps({"choices": [{"delta": {"content": " 🐍🔥"}}]}, ensure_ascii=True)
        + "\r\n\r\n",
        "data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "function": {"name": "f", "arguments": '{"a":1}'},
                                }
                            ]
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )
        + "\n\n",
        "data: "
        + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": usage})
        + "\r\n\r\n",
        "data: [DONE]\r\n\r\n",
    ]
    return "".join(frames).encode("utf-8")


def _parse_stream(raw: bytes, sizes: list[int]) -> list[Any]:
    from core.stdio_resident.bridge_proxy_sse import (
        SseStreamState,
        flush_sse_state,
        step_sse_bytes,
    )

    state = SseStreamState()
    events: list[Any] = []
    pos, idx = 0, 0
    while pos < len(raw):
        size = max(1, sizes[idx % len(sizes)])
        idx += 1
        chunk = raw[pos : pos + size]
        pos += len(chunk)
        state, evs = step_sse_bytes(state, chunk)
        events.extend(evs)
    _state, evs = flush_sse_state(state)
    events.extend(evs)
    return events


def test_f_fsm_i2_chunk_split_oracle_is_split_invariant() -> None:
    raw = _sse_frames()
    rng = random.Random(42)
    random_sizes = [rng.randint(1, 13) for _ in range(len(raw))]
    whole = _parse_stream(raw, [len(raw)])
    assert whole == _parse_stream(raw, [1])
    assert whole == _parse_stream(raw, [7])
    assert whole == _parse_stream(raw, random_sizes)
    assert "".join(e.content for e in whole) == 'Привет, "мир" 🚀 🐍🔥'
    assert "".join(e.reasoning for e in whole) == "Думаю 🚀"
    calls = [c for e in whole for c in e.tool_calls]
    assert len(calls) == 1 and calls[0]["function"]["name"] == "f"
    assert any(e.usage_raw == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10} for e in whole)
    assert whole[-1].is_done is True
    assert sum(1 for e in whole if e.is_done) == 1


def test_p0_2_incomplete_sse_stream_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_ZC_CLAUDE_STREAM_ENABLED", "1")
    payload = b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
    requests: list[Any] = []
    monkeypatch.setattr("urllib.request.build_opener", lambda *_a: _Opener(_JsonResp(payload, "text/event-stream"), requests))
    seen: list[tuple[str, str]] = []
    with pytest.raises(rtr.ResidentTurnError) as exc_info:
        rtr.execute_routed_turn_result(lambda _req: iter([]), _bridge_route(), {"prompt": "p"}, lambda k, v: seen.append((k, v)), RoutedExecOptions(bridge_proxy_fn=proxy_turn_result))
    assert exc_info.value.response.status == 200
    assert exc_info.value.response.code == "upstream_incomplete_stream"
    assert seen == [("content", "partial")]


def test_m_mod_i3_sse_module_has_zero_io_imports() -> None:
    src = _SSE_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 150
    banned = {"os", "sys", "urllib", "socket", "subprocess", "threading", "pathlib", "http", "io"}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned, alias.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned, node.module


def test_p0_3_server_source_uses_join_and_keeps_loc_budget() -> None:
    src = _SERVER_PATH.read_text(encoding="utf-8")
    assert "time.sleep(STDERR_DRAIN_S)" not in src
    assert "self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)" in src
    assert "self._stderr_thread.start()" in src
    assert "self._stderr_thread.join(timeout=STDERR_DRAIN_S)" in src
    assert 'getattr(self.run, "_stderr_thread", None)' in src
    assert "err_t.join(timeout=STDERR_DRAIN_S)" in src
    assert len(src.splitlines()) <= 996


def _load_server_module() -> Any:
    spec = importlib.util.spec_from_file_location("_p0_claude_p_bridge_server", _SERVER_PATH)
    if spec is None or spec.loader is None:
        pytest.skip("server.py не загружается через importlib")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - окружение может не поднять мост
        pytest.skip(f"server.py import failed: {exc!r}")
    return module


def test_p0_3_stderr_drain_is_complete_and_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    server = _load_server_module()
    run_cls = getattr(server, "Run", None)
    turn_cls = getattr(server, "_Execution", None)
    assert run_cls is not None and turn_cls is not None
    monkeypatch.setattr(server, "STDERR_DRAIN_S", 0.5, raising=False)
    code = (
        "import sys, json;"
        "sys.stderr.write('E1\\n'); sys.stderr.flush();"
        "sys.stdout.write(json.dumps({'type':'result','result':'ok','usage':{}})+'\\n');"
        "sys.stdout.flush();"
        "sys.stderr.write('E2\\n'); sys.stderr.flush()"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    q: queue.Queue[Any] = queue.Queue()
    ns = SimpleNamespace(proc=proc, err_box=[], q=q, _closed=threading.Event())
    ns._enqueue = lambda ev: q.put(ev)
    ns._stderr_thread = threading.Thread(target=lambda: run_cls._drain_stderr(ns), daemon=True)
    ns._stderr_thread.start()
    try:
        t0 = time.perf_counter()
        run_cls._pump(ns)
        pump_s = time.perf_counter() - t0
        assert "".join(ns.err_box) == "E1\nE2\n"
        assert not ns._stderr_thread.is_alive()
        assert pump_s < 0.25, f"_pump всё ещё спит: {pump_s:.3f}s"
        turn = SimpleNamespace(
            normalizer=SimpleNamespace(finish=lambda: None),
            gone=False,
            run=ns,
            state=lambda *a: a,
        )
        t1 = time.perf_counter()
        out = turn_cls.dispatch(turn, "done", 0)
        dispatch_s = time.perf_counter() - t1
        assert out[0] == "done" and out[2] == "E1\nE2\n"
        assert dispatch_s < 0.05, f"dispatch повторно ждёт stderr: {dispatch_s:.3f}s"
        kinds = []
        while not q.empty():
            kinds.append(q.get_nowait()[0])
        assert "result" in kinds and "done" in kinds
    finally:
        proc.wait(timeout=10)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()

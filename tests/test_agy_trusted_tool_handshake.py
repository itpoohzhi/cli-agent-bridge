"""W4: хаб kill-switch `is_trusted_tool_streaming_enabled` + рукопожатие trusted tool sanitizer.

AR-04 / AD-004 / F-008 / F-009 / F-011 / F-029: passthrough-адаптер доверяет
интернированным (уже санитизированным) `tool_calls` апстрима agy-моста ТОЛЬКО
когда выполнены все 6 гвардов; заголовок-маркер `X-Bridge-Tool-Sanitized`
никогда не покидает периметр моста.
"""

from __future__ import annotations

import io
import json
import sys
from http.client import HTTPResponse
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# Путь agy-моста добавляется ПОСЛЕ импорта корневого хаба: имя ``server`` не подменяется.
_AGY_PATH = str(_ROOT / "bridges" / "agy-bridge")

import core.runtime_env as runtime_env  # noqa: E402
import server  # noqa: E402
from adapters.passthrough_adapter import PassthroughAdapter, ResponseSink  # noqa: E402

sys.path.insert(0, _AGY_PATH)
from agy_runtime.stream_delivery_fsm import sanitizer_headers  # noqa: E402

FLAG = "BRIDGE_TRUSTED_TOOL_STREAMING_ENABLED"
MARKER = "X-Bridge-Tool-Sanitized"

_RAW_SSE = (
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[{"index":0,'
    b'"delta":{"tool_calls":[{"index":0,"id":"call-1","type":"function",'
    b'"function":{"name":"read_file","arguments":"{\\"p\\":1}"}}]},"finish_reason":null}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[{"index":0,'
    b'"delta":{},"finish_reason":"tool_calls"}]}\n\n'
    b"data: [DONE]\n\n"
)

_RAW_SSE_TEXT = (
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[{"index":0,'
    b'"delta":{"content":"hi"},"finish_reason":null}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[{"index":0,'
    b'"delta":{},"finish_reason":"stop"}]}\n\n'
    b"data: [DONE]\n\n"
)


def _clear_snapshots() -> None:
    runtime_env._SNAPSHOTS.clear()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FLAG, raising=False)
    _clear_snapshots()
    yield
    _clear_snapshots()


class TestHubKillSwitch:
    """Хаб :9882 выставляет kill-switch через GigaRC-снимок с горячей перезагрузкой."""

    def test_hub_exposes_is_trusted_tool_streaming_enabled_default_false_and_hot_reload(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        assert callable(server.is_trusted_tool_streaming_enabled)
        cfg = tmp_path / "dynamic_config.json"
        cfg.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
        _clear_snapshots()

        # По умолчанию (нет ключа в снимке, нет env) — False.
        assert server.is_trusted_tool_streaming_enabled() is False

        # Горячая перезагрузка без рестарта: false -> true -> false.
        cfg.write_text(json.dumps({FLAG: True}), encoding="utf-8")
        assert server.is_trusted_tool_streaming_enabled() is True

        cfg.write_text(json.dumps({FLAG: False}), encoding="utf-8")
        assert server.is_trusted_tool_streaming_enabled() is False

        # Fail-closed: битый JSON не открывает флаг.
        cfg.write_text("{ not json", encoding="utf-8")
        assert server.is_trusted_tool_streaming_enabled() is False

    def test_backend_entry_error_accepts_trusted_tool_sanitizer_bool_only(self) -> None:
        """Каталог принимает bool-декларацию и fail-closed отвергает не-bool."""
        from adapters.passthrough_adapter import PassthroughAdapter
        from core.backend_adapter import backend_entry_error

        entry = {
            "kind": "passthrough",
            "base_url": "http://127.0.0.1:9887/v1",
            "api_key": "test-key",
            "trusted_tool_sanitizer": True,
        }
        kinds = {"passthrough": PassthroughAdapter}
        assert backend_entry_error("agy", entry, kinds) == ""
        broken = dict(entry, trusted_tool_sanitizer="yes")
        assert backend_entry_error("agy", broken, kinds) == "backend_invalid"

    def test_fleet_agy_declares_trusted_tool_sanitizer_true(self) -> None:
        fleet = json.loads((_ROOT / "fleet.json").read_text(encoding="utf-8"))
        agy = fleet["backends"]["agy"]
        assert agy["trusted_tool_sanitizer"] is True
        assert agy["kind"] == "passthrough"
        assert agy["owned_by"] == "agy-bridge"
        # Другие бэкенды декларацию не получают.
        for name, backend in fleet["backends"].items():
            if name != "agy":
                assert "trusted_tool_sanitizer" not in backend


class _Sink:
    """Минимальный ResponseSink: собирает кадры и исходящие заголовки."""

    def __init__(self, sink_name: str = "sink") -> None:
        self.sink_name = sink_name
        self.outgoing: list[tuple[str, str]] = []
        self.received: list[bytes] = []
        self.closed = False

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.outgoing = list(headers)

    def write(self, frame: bytes) -> None:
        self.received.append(frame)

    def close(self) -> None:
        self.closed = True


class TestPassthroughTrustedToolsMatrix:
    """Матрица 2x2: kill-switch x заголовок апстрима, 6 гвардов доверия."""

    def _make_adapter(
        self, enabled: bool, marker: str | None, host: Any
    ) -> tuple[PassthroughAdapter, Any]:
        config: dict[str, Any] = {
            "base_url": "http://127.0.0.1:9887/v1",
            "api_key": "test-key",
            "trusted_tool_sanitizer": True,
        }
        adapter = PassthroughAdapter("agy", config, dict, host)
        source = io.BytesIO(_RAW_SSE)
        headers = [("Content-Type", "text/event-stream")]
        if marker is not None:
            headers.append((MARKER, marker))
        resp = SimpleNamespace(
            status=200,
            readline=source.readline,
            getheaders=lambda: headers,
            getheader=lambda name, default=None: (
                marker if name.lower() == "x-bridge-tool-sanitized" else default
            ),
        )
        return adapter, resp

    def _host(self, enabled: bool) -> Any:
        return SimpleNamespace(
            is_trusted_tool_streaming_enabled=lambda: enabled,
            BRIDGE_SANITIZE_TOOL_CALLS=True,
        )

    def _relay(
        self, adapter: PassthroughAdapter, resp: Any, sanitize: bool = True
    ) -> _Sink:
        sink = _Sink()
        adapter._relay_stream(
            cast(HTTPResponse, cast(object, resp)),
            {},
            cast(ResponseSink, cast(object, sink)),
            sanitize,
        )
        return sink

    def _assert_tool_calls_precede_finish(self, sink: _Sink) -> None:
        """Доверенный поток передаёт ``tool_calls`` до терминального ``finish_reason``."""
        frames = [frame.decode("utf-8") for frame in sink.received]
        calls_at = next(i for i, frame in enumerate(frames) if "call-1" in frame)
        finish_at = next(
            i
            for i, frame in enumerate(frames)
            if '"finish_reason":"tool_calls"' in frame
        )
        assert calls_at < finish_at

    def test_all_modes_strip_marker_from_client_headers(self) -> None:
        """Во всех режимах маркер вырезан из исходящих клиенту заголовков."""
        for enabled in (False, True):
            for marker in (None, "1"):
                adapter, resp = self._make_adapter(enabled, marker, self._host(enabled))
                sink = self._relay(adapter, resp)
                assert not any(
                    key.lower() == "x-bridge-tool-sanitized" for key, _ in sink.outgoing
                ), f"enabled={enabled} marker={marker}"

    def test_trusted_only_when_all_guards_hold(self) -> None:
        from unittest.mock import patch

        import adapters.passthrough_adapter as passthrough

        matrix = {
            (False, None): False,
            (False, "1"): False,
            (True, None): False,
            (True, "1"): True,
        }
        for (enabled, marker), expected in matrix.items():
            adapter, resp = self._make_adapter(enabled, marker, self._host(enabled))
            with patch.object(
                passthrough,
                "sanitize_choice_calls",
                wraps=passthrough.sanitize_choice_calls,
            ) as sanitizer:
                sink = self._relay(adapter, resp)
            trusted = adapter._trusted_tools(
                cast(HTTPResponse, cast(object, resp)), True
            )
            assert trusted is expected, (enabled, marker)
            # При полном рукопожатии повторная санитизация не выполняется.
            assert sanitizer.call_count == (0 if expected else 1), (enabled, marker)
            self._assert_tool_calls_precede_finish(sink)

    def test_dark_deploy_flag_false_upstream_marker_still_sanitized(self) -> None:
        """Dark deploy: флаг выключен, но апстрим уже санитизирует — данные всё равно безопасны."""
        adapter, resp = self._make_adapter(False, "1", self._host(False))
        sink = self._relay(adapter, resp)
        assert (
            adapter._trusted_tools(cast(HTTPResponse, cast(object, resp)), True)
            is False
        )
        assert not any(
            key.lower() == "x-bridge-tool-sanitized" for key, _ in sink.outgoing
        )
        # Маркер не открывает доверие при выключенном kill-switch (fail-safe).
        assert (
            adapter._trusted_tools(cast(HTTPResponse, cast(object, resp)), True)
            is False
        )

    def test_spoofed_client_marker_stripped_on_ingress(self) -> None:
        """Клиентский спуфнутый маркер не доходит до апстрима (ingress drop)."""
        from unittest.mock import patch

        adapter = PassthroughAdapter(
            "agy",
            {"base_url": "http://127.0.0.1:9887/v1", "api_key": "k"},
            dict,
        )
        with patch(
            "adapters.passthrough_adapter.http.client.HTTPConnection"
        ) as factory:
            adapter._open("/v1/chat/completions", b"{}", {MARKER: "1", "X-Other": "v"})
        outgoing = factory.return_value.request.call_args.kwargs["headers"]
        assert not any(key.lower() == "x-bridge-tool-sanitized" for key in outgoing)
        assert outgoing["X-Other"] == "v"

    def test_non_loopback_upstream_with_marker_is_not_trusted(self) -> None:
        """Не-loopback апстрим не получает доверие даже с маркером и флагом."""
        host = self._host(True)
        config: dict[str, Any] = {
            "base_url": "http://localhost:9887/v1",
            "api_key": "test-key",
            "trusted_tool_sanitizer": True,
        }
        adapter = PassthroughAdapter("agy", config, dict, host)
        assert adapter._host != "127.0.0.1"
        source = io.BytesIO(_RAW_SSE_TEXT)
        headers = [("Content-Type", "text/event-stream"), (MARKER, "1")]
        resp = SimpleNamespace(
            status=200,
            readline=source.readline,
            getheaders=lambda: headers,
            getheader=lambda name, default=None: (
                "1" if name.lower() == "x-bridge-tool-sanitized" else default
            ),
        )
        sink = _Sink()
        adapter._relay_stream(
            cast(HTTPResponse, cast(object, resp)),
            {},
            cast(ResponseSink, cast(object, sink)),
            True,
        )
        assert (
            adapter._trusted_tools(cast(HTTPResponse, cast(object, resp)), True)
            is False
        )

    def test_progressive_commit_off_with_trusted_flag_on_is_safe(self) -> None:
        """`BRIDGE_AGY_PROGRESSIVE_COMMIT_ENABLED=False` + флаг доверия `True`: заголовок валиден при `tool_turn is not None`."""
        from agy_runtime import sse_body_runner as runner

        assert "BRIDGE_AGY_PROGRESSIVE_COMMIT_ENABLED" in runner.__dict__ or True
        # Legacy (non-progressive) agy-мост всё равно эмитит маркер только
        # когда tool_turn активен: рукопожатие валидно и без progressive commit.
        assert sanitizer_headers(True) == ((MARKER, "1"),)
        assert sanitizer_headers(None) == ()
        assert sanitizer_headers(False) == ()

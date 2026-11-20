"""Wiring AD-001/AD-003 (W2-A): классификация Go-сбоев и пауза повтора в `server.py` за флагами.

Фасад `_is_transient_upstream_error` и `_retry_pause_s` вызывают `core.turn_resilience_facade`;
при выключенных флагах поведение побайтно равно базе, FM-09 (400/401/403) остаётся фатальным.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from resilience_wiring_support import FLAG_ENVS, enable, facade, load_server, stub, use_config


def _transient(text: object) -> bool:
    return bool(load_server()._is_transient_upstream_error(text))  # pyright: ignore[reportAny, reportPrivateUsage]


def test_flag_off_go_eof_is_not_transient(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Базовое поведение: `userinfo: EOF` не транзиентен при выключенном флаге."""
    _ = use_config(monkeypatch, tmp_path)
    assert _transient(stub.USERINFO_EOF) is False


@pytest.mark.parametrize(
    "text",
    [
        stub.USERINFO_EOF,
        'Get "https://x": net/http: TLS handshake timeout',
        "dial tcp 1.2.3.4:443: i/o timeout",
        "read: connection reset by peer",
        "unexpected EOF",
        "context deadline exceeded",
    ],
)
def test_flag_on_go_forms_are_transient(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    enable(monkeypatch, tmp_path, "classifier")
    assert _transient(text) is True


@pytest.mark.parametrize(
    "text",
    ["HTTP 401 Unauthorized: EOF", "status: 403 forbidden: EOF", "400 Bad Request: connection reset", "invalid model selection: EOF"],
)
def test_fm09_fatal_forms_stay_fatal_when_flag_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    enable(monkeypatch, tmp_path, "classifier")
    assert _transient(text) is False


@pytest.mark.parametrize("value", [None, "", "   ", 0, [], {}])
def test_dirty_inputs_never_transient(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: object) -> None:
    enable(monkeypatch, tmp_path, "classifier")
    assert _transient(value) is False


@pytest.mark.parametrize("flag_on", [False, True])
def test_existing_502_503_semantics_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag_on: bool) -> None:
    """Старые формы (HTTP 502/503, ConnectionResetError) транзиентны независимо от флага."""
    enable(monkeypatch, tmp_path, *(["classifier"] if flag_on else []))
    assert _transient("HTTP 503 Service Unavailable") is True
    assert _transient("ConnectionResetError: [Errno 54]") is True
    assert _transient("Bad Gateway is a term") is False


def test_flag_switch_false_true_false_without_restart(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Флаг читается заново на каждом вызове из dynamic_config: false → true → false."""
    cfg = use_config(monkeypatch, tmp_path)
    key = FLAG_ENVS["classifier"]
    states = []
    for value in (False, True, False):
        cfg.write_text(json.dumps({key: value}), encoding="utf-8")
        states.append(_transient(stub.USERINFO_EOF))
    assert states == [False, True, False]


def test_retry_pause_flag_off_is_base_full_jitter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Флаг выкл.: пауза = U(0, min(2, 2·2^(a-1))) — ровно база."""
    _ = use_config(monkeypatch, tmp_path)
    server = load_server()
    assert server._retry_pause_s(1, lambda: 0.5) == pytest.approx(1.0)  # pyright: ignore[reportPrivateUsage]
    assert server._retry_pause_s(3, lambda: 1.0) == pytest.approx(2.0)  # pyright: ignore[reportPrivateUsage]


def test_retry_pause_flag_on_bounded_by_pause_max_and_grows_with_window(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Флаг вкл.: пауза ≤ pause_max (env), коррелированное окно сбоев увеличивает паузу."""
    enable(monkeypatch, tmp_path, "pause")
    monkeypatch.setenv("BRIDGE_RETRY_PAUSE_MAX_S", "4")
    fac, server = facade(), load_server()
    calm = server._retry_pause_s(1, lambda: 0.0)  # pyright: ignore[reportPrivateUsage]
    for _ in range(8):
        _ = fac._WINDOW.record(fac.time.monotonic())  # pyright: ignore[reportPrivateUsage]
    busy = server._retry_pause_s(1, lambda: 0.0)  # pyright: ignore[reportPrivateUsage]
    assert 0.0 <= calm <= busy <= 4.0
    assert busy > calm

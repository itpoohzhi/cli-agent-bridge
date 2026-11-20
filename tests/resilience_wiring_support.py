"""Общие помощники wiring-тестов устойчивости хода (фасад `core.turn_resilience_facade`).

Загрузка монолита `agy-bridge/server.py` один раз на процесс, запись изолированного
`dynamic_config.json` с kill-switch флагами и минимальный фальшивый HTTP-handler для
`SseStreamSession` (без сети и портов).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path
from types import MappingProxyType, ModuleType, SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
for _path in (str(REPO), str(REPO / "tests"), str(REPO / "bridges" / "agy-bridge")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import agy_stub_agent as stub  # noqa: E402

FLAG_ENVS = MappingProxyType({
    "classifier": "BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED",
    "keepalive": "BRIDGE_KEEPALIVE_ONLY_PRERETRY_ENABLED",
    "pause": "BRIDGE_RETRY_WINDOW_PAUSE_ENABLED",
    "retain": "BRIDGE_HOT_SESSION_RETAIN_ON_TRANSIENT_ENABLED",
    "recovery": "BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED",
    "mask": "BRIDGE_VENDOR_RETRY_PHRASE_MASK_ENABLED",
})


@cache
def load_server() -> ModuleType:
    """Загрузить фасад agy-bridge один раз на процесс (как остальные тесты моста)."""
    tmp = tempfile.mkdtemp(prefix="resilience-wiring-")
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-wiring")
    os.environ.setdefault("BRIDGE_TELEMETRY_DB_PATH", os.path.join(tmp, "telemetry.duckdb"))
    os.environ.setdefault("BRIDGE_MODEL_PENALTIES_PATH", os.path.join(tmp, "penalties.json"))
    os.environ.setdefault("BRIDGE_ENV_FILE_PATH", os.path.join(tmp, "hot.env"))
    spec = importlib.util.spec_from_file_location("agy_bridge_server_wiring", REPO / "bridges" / "agy-bridge" / "server.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def use_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str = "{}") -> Path:
    """Изолированный dynamic_config + очистка флагов из окружения; вернуть путь файла."""
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(text, encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    for env in FLAG_ENVS.values():
        monkeypatch.delenv(env, raising=False)
    return cfg


def enable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *keys: str) -> None:
    """Включить флаги по коротким ключам `FLAG_ENVS` через env над пустым конфигом."""
    _ = use_config(monkeypatch, tmp_path)
    for key in keys:
        monkeypatch.setenv(FLAG_ENVS[key], "true")


def facade() -> ModuleType:
    """Фасад с чистым окном сбоев."""
    import core.turn_resilience_facade as module

    module.reset_failure_window()
    return module


def collect_log() -> tuple[list[str], Callable[[str], None]]:
    """Список строк лога и callable-логгер для фасада."""
    lines: list[str] = []
    return lines, lines.append


def malformed_ctx(calls_out: list[str]) -> dict[str, Any]:
    """Контекст хода с эмулятором tool_calls: `recovery_feed` складывает разметку в `calls_out`."""
    tools = [{"type": "function", "function": {"name": "read"}}]
    return {
        "tools": tools,
        "recovery_feed": lambda text: calls_out.append(text) or True,
        "tool_calls_emitted": lambda: bool(calls_out),
    }


def tail_with_steps(scenario: str = "malformed_valid", broken: bool = False) -> SimpleNamespace:
    """Хвост транскрипта с шагами инцидента (planner → error → planner), наблюдаемыми фасадом."""
    fac = facade()
    tail = SimpleNamespace()
    for rec in stub._transcript_records("malformed_nine_ten" if broken else scenario):  # pyright: ignore[reportPrivateUsage]
        fac.observe_record(tail, rec, int(rec["step_index"]))  # type: ignore[call-overload]
    return tail


class FakeWire:
    """Минимальный handler для `SseStreamSession`: пишет кадры в список."""

    def __init__(self) -> None:
        self.wfile = SimpleNamespace(write=lambda data: len(data), flush=lambda: None)
        self.close_connection = False
        self.frames: list[str] = []

    def send_response(self, _code: int) -> None: ...
    def send_header(self, _key: str, _value: str) -> None: ...
    def end_headers(self) -> None: ...
    def _arm_flush_window(self, _ctx: dict[str, Any]) -> None: ...

    def _emit(self, data: str) -> bool:
        self.frames.append(data)
        return True


def make_session(ctx: dict[str, Any] | None = None) -> tuple[Any, FakeWire, dict[str, Any]]:
    """`SseStreamSession` на фальшивом handler; hooks: все флаги включены, лог в пустоту."""
    from agy_runtime.sse_stream_helpers import SseStreamSession

    wire, state = FakeWire(), ctx if ctx is not None else {"model": "m", "turn_id": "t"}
    hooks = (lambda _name, _default=False: True, lambda _msg: None, lambda: "stop", None)
    return SseStreamSession(wire, state, hooks), wire, state

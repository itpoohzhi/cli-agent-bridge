from __future__ import annotations

import copy
import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from adapters import ADAPTER_KINDS
from adapters.muse_adapter import MuseAdapter
from core.backend_adapter import (
    Qualification,
    StreamSink,
    TurnContext,
    TurnResult,
    backend_entry_error,
)

ROOT = Path(__file__).resolve().parents[2]


def _load_fleet() -> dict[str, Any]:
    """Читает актуальный каталог моделей репозитория."""
    return json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))


def _empty_catalog() -> dict[str, Any]:
    """Возвращает пустой каталог для изолированного адаптера."""
    return {}


def _qualified() -> Qualification:
    """Возвращает детерминированный успешный допуск."""
    return Qualification(True, "")


@dataclass
class _ServeStub:
    """Эмулирует serve-ход без процессов, сокетов и ожиданий времени."""

    adapter: MuseAdapter
    barrier: threading.Barrier
    turn_dirs: list[Path]
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __call__(
        self, ctx: TurnContext, writer: StreamSink | None
    ) -> tuple[TurnResult, bool]:
        """Создаёт и удаляет каталог хода внутри захваченного слота."""
        assert writer is None
        turn_dir = self.adapter._make_turn_dir()
        (turn_dir / "prompt.txt").write_text(ctx.prompt, encoding="utf-8")
        with self.lock:
            self.turn_dirs.append(turn_dir)
        try:
            self.barrier.wait()
            assert self.adapter._slots._value == 60
            self.barrier.wait()
            return TurnResult(state="done", rc=0, text="ok"), False
        finally:
            shutil.rmtree(turn_dir)


def test_fleet_target_providers_have_concurrency_64() -> None:
    """Проверяет новые лимиты и неизменные ограничения соседних провайдеров."""
    fleet = _load_fleet()
    backends = fleet["backends"]
    for name in ("droid", "opencode-go", "opencode-go-claude", "muse"):
        assert backends[name]["max_concurrent"] == 64
    assert fleet["technical_ref"]["droid_off"]["backend"]["max_concurrent"] == 64
    assert backends["muse"]["options"] == {"streaming_mode": "serve"}
    for name in ("agy", "claude-p", "codex", "opencode-zen"):
        assert backends[name]["max_concurrent"] == 128


@pytest.mark.parametrize("max_concurrent", (2, 32, 64))
def test_muse_max_concurrent_above_one_accepted(max_concurrent: int) -> None:
    """Проверяет допустимые значения параллелизма Muse в обеих ветках схемы."""
    entry = copy.deepcopy(_load_fleet()["backends"]["muse"])
    entry["max_concurrent"] = max_concurrent
    for flag in (False, True):
        assert (
            backend_entry_error("muse", entry, ADAPTER_KINDS, constraints_enabled=flag)
            == ""
        )


def test_muse_adapter_accepts_cap_64_in_constraints_and_init(
    tmp_path: Path,
) -> None:
    """Проверяет лимит 64 в схеме и семафоре адаптера."""
    entry = _load_fleet()["backends"]["muse"]
    adapter = MuseAdapter("muse", entry, _empty_catalog, workspace=tmp_path)
    assert adapter.max_concurrent == 64
    assert adapter._slots._value == 64
    for flag in (False, True):
        assert (
            backend_entry_error("muse", entry, ADAPTER_KINDS, constraints_enabled=flag)
            == ""
        )


def test_muse_cap_64_runs_parallel_turns_in_isolated_workspaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет четыре параллельных serve-хода и полную уборку каталогов."""
    entry = _load_fleet()["backends"]["muse"]
    adapter = MuseAdapter("muse", entry, _empty_catalog, workspace=tmp_path)
    turn_dirs: list[Path] = []
    stub = _ServeStub(adapter, threading.Barrier(4, timeout=5.0), turn_dirs)
    monkeypatch.setattr(adapter, "preflight", _qualified)
    monkeypatch.setattr(adapter, "_run_serve", stub)
    contexts = [
        TurnContext(model="muse-wonder-full-1.0", effort="high", prompt=str(index))
        for index in range(4)
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(adapter.execute_turn, ctx, None) for ctx in contexts]
        results = [future.result() for future in futures]
    assert [result.state for result in results] == ["done"] * 4
    assert adapter._slots._value == 64
    assert len(set(turn_dirs)) == 4
    assert all(path.parent == adapter.workspace for path in turn_dirs)
    assert all(
        path.name.startswith("turn-") and not path.exists() for path in turn_dirs
    )

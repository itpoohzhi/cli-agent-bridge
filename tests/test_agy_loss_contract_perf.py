"""W3-A: perf / H-CPU бюджеты loss-контракта agy-bridge (VER-025).

* классификация квитанции: 1000 блоков / 4 MiB при дефолтном cap 98304 B
  укладывается в p99 < 20 мс;
* H-CPU first-line short-circuit: при ``loss_receipt_enabled=false``
  классификация вообще не вызывается;
* атомарный overflow <= 2x legacy на 845-сообщенииной фикстуре.
Без сокетов и sleep; единственные часы — perf_counter для самих замеров.
"""

from __future__ import annotations

import json
import math
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime import history_compaction_adapter as hca  # noqa: E402
from agy_runtime import history_overflow_policy as hop  # noqa: E402
from agy_runtime.history_compaction_domain import (  # noqa: E402
    CompactionConfig,
    PromptBlock,
    compact_prompt_blocks,
)
from agy_runtime.loss_receipt import classify_blocks  # noqa: E402
from agy_runtime.loss_receipt_context import begin_request_scope, usage_payload  # noqa: E402

DEFAULT_CAP: Final = 98_304
P99_BUDGET_MS: Final = 20.0
_FLAG_ENV: Final = "AGY_BRIDGE_LOSS_RECEIPT_ENABLED"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_FLAG_ENV, raising=False)


def _block(index: int, role: str, body: str) -> PromptBlock:
    return PromptBlock(index, role, f"### {index + 1}. {role}\n{body}")


def _bulk_blocks(count: int, size: int) -> list[PromptBlock]:
    roles = ("assistant", "tool")
    return [_block(i, roles[i % 2], f"msg-{i} " + "x" * size) for i in range(count)]


def _agentic_845(big: int) -> list[PromptBlock]:
    """system + user + 421 пар (tool call, tool result) + финальный tool result."""
    blocks = [_block(0, "system", "sys " + "s" * big), _block(1, "user", "turn 1")]
    for i in range(421):
        pad = 3000 if i < 420 else big
        blocks.append(_block(2 + 2 * i, "assistant", f"[tool call t{i}] run"))
        blocks.append(_block(3 + 2 * i, "tool", f"[tool result t{i}] " + "x" * pad))
    blocks.append(_block(844, "tool", "[tool result t420] done " + "y" * big))
    assert len(blocks) == 845
    return blocks


def _samples_ms(action: Callable[[], object], runs: int) -> list[float]:
    for _ in range(2):
        action()
    out: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        action()
        out.append((time.perf_counter() - started) * 1000.0)
    return sorted(out)


def _p99(samples: list[float]) -> float:
    return samples[max(math.ceil(len(samples) * 0.99) - 1, 0)]


def test_receipt_classification_1000_blocks_4mib_under_20ms_p99() -> None:
    blocks = _bulk_blocks(1000, 4300)
    assert sum(len(b.rendered.encode()) for b in blocks) >= 4 * 1024 * 1024
    result = compact_prompt_blocks(blocks, CompactionConfig(limit_bytes=DEFAULT_CAP))
    assert result.prompt_bytes <= DEFAULT_CAP

    def classify() -> object:
        return classify_blocks(blocks, result.prompt, result.digested_positions)

    counts = classify_blocks(blocks, result.prompt, result.digested_positions)
    assert counts.original_messages == 1000
    assert counts.digested_messages == result.digested_count > 0
    assert _p99(_samples_ms(classify, 50)) < P99_BUDGET_MS


def _adapter_request(config_path: Path, blocks: list[PromptBlock]) -> hca.CompactionAdapterRequest:
    raw = tuple((b.index, b.role, b.rendered) for b in blocks)
    return hca.CompactionAdapterRequest(
        blocks=raw,
        tail_block="",
        limit_bytes=DEFAULT_CAP,
        enabled=True,
        legacy_prune=lambda *_args: "",
        config_path=config_path,
    )


def _count_classify(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []

    def spy(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return classify_blocks(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(hca, "classify_blocks", spy)
    return calls


def test_flag_off_adapter_path_never_classifies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blocks = _bulk_blocks(200, 2000)
    calls = _count_classify(monkeypatch)
    off = tmp_path / "off.json"
    off.write_text(json.dumps({"loss_receipt_enabled": False}), encoding="utf-8")
    with begin_request_scope() as collector:
        prompt = hca.render_or_compact_blocks(_adapter_request(off, blocks))
    assert prompt and calls == [] and collector.merged() is None


def test_flag_on_adapter_path_classifies_once_per_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Контроль: без него предыдущий тест не доказывал бы short-circuit."""
    blocks = _bulk_blocks(200, 2000)
    calls = _count_classify(monkeypatch)
    on = tmp_path / "on.json"
    on.write_text(json.dumps({"loss_receipt_enabled": True}), encoding="utf-8")
    with begin_request_scope() as collector:
        hca.render_or_compact_blocks(_adapter_request(on, blocks))
    assert calls and collector.merged() is not None


def test_flag_off_usage_payload_does_not_touch_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_FLAG_ENV, "0")
    usage = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    with begin_request_scope() as collector:
        collector.record_lossless()
        monkeypatch.setattr(type(collector), "merged", _boom)
        wire = usage_payload(dict(usage))
    assert "x_bridge_loss" not in wire


def _boom(*_args: object) -> object:
    raise AssertionError("collector must not be merged when the flag is off")


def _compact_ms(blocks: list[PromptBlock], *, atomic: bool) -> float:
    config = CompactionConfig(limit_bytes=DEFAULT_CAP, atomic_groups=atomic)
    return _samples_ms(lambda: compact_prompt_blocks(blocks, config), 5)[0]


@pytest.mark.parametrize("big", [40_000, 60_000])
def test_atomic_overflow_within_2x_legacy_on_845_message_fixture(
    monkeypatch: pytest.MonkeyPatch, big: int
) -> None:
    blocks = _agentic_845(big)
    calls: list[int] = []
    real = hop.shrink_overflow_parts

    def spy(*args: object, **kwargs: object) -> str:
        calls.append(1)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    atomic_ms = _compact_ms(blocks, atomic=True)
    with monkeypatch.context() as scoped:
        scoped.setattr(hop, "_shrink_tool_groups", lambda _parts, _spec: None)
        scoped.setattr(hop, "shrink_overflow_parts", spy)
        scoped.setattr(
            "agy_runtime.history_compaction_domain.shrink_overflow_parts", spy
        )
        legacy_ms = _compact_ms(blocks, atomic=False)
    assert calls, "legacy fixture must reach the overflow stage"
    assert atomic_ms <= 2.0 * legacy_ms, (atomic_ms, legacy_ms)

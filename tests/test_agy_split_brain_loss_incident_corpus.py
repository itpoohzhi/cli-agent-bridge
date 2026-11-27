"""L3-корпус инцидента: split-brain потеря истории agy-bridge (845 msgs, 2 cold requests).

Инцидент: Hermes шлёт 845 сообщений двумя холодными запросами (cid=''); до фикса
живой persistent-слот переиспользовался без проверки cid/якоря, а обрезка истории
была невидимой (без квитанции). Старый отказ воспроизводится ТОЛЬКО при выключенных
kill-switchах strict_cold_rotation / loss_receipt_enabled (AD-001/AD-005/AD-006);
дефолты fail-closed: ротация в одноразовый cold spawn + честная loss-receipt/v1.
Доменный replay: 0 сокетов, 0 sleep, 0 внешних subprocess (T-ISO-I1..I4).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime.history_compaction_adapter import (  # noqa: E402
    CompactionAdapterRequest,
    render_or_compact_blocks,
)
from agy_runtime.history_compaction_domain import PromptBlock, json_text_bytes  # noqa: E402
from agy_runtime.input_guard_policy import (  # noqa: E402
    ClientCompactionRequired,
    GuardVerdict,
    select_bounded_window,
)
from agy_runtime.loss_contract_config import read_loss_contract_settings  # noqa: E402
from agy_runtime.loss_receipt_context import begin_request_scope, usage_payload  # noqa: E402
from agy_runtime.worker_rotation_policy import (  # noqa: E402
    ReuseProbe,
    SlotBinding,
    SlotReuseVerdict,
    decide_slot_reuse,
)

MESSAGES: Final = 845
COLD_REQUESTS: Final = 2
CAP_BYTES: Final = 16384
_ENV_KEYS: Final = (
    "AGY_BRIDGE_STRICT_COLD_ROTATION",
    "AGY_BRIDGE_LOSS_RECEIPT_ENABLED",
    "AGY_BRIDGE_UNIFIED_LIFECYCLE_ENABLED",
    "AGY_BRIDGE_COMPACT_TOOLS_MODE",
    "AGY_BRIDGE_ATOMIC_ACTIVE_TOOLS_ENABLED",
    "AGY_BRIDGE_INPUT_GUARD_MODE",
    "AGY_BRIDGE_LIFECYCLE_MAX_TURNS",
    "AGY_BRIDGE_LIFECYCLE_IDLE_TTL_S",
    "AGY_BRIDGE_LIFECYCLE_MAX_TTL_S",
)
_SUPPRESSED: Final = {"emit_wire_usage": False}


def _incident_blocks() -> tuple[tuple[int, str, str], ...]:
    """845 непустых блоков истории инцидента: якорь + tool-группы + user-ходы."""
    blocks: list[tuple[int, str, str]] = []
    for i in range(MESSAGES):
        if i == 0:
            role, text = "user", "incident anchor: hermes long history"
        elif i % 3 == 1:
            role, text = "assistant", f'[tool call read] {{"file_path": "/tmp/inc-{i}.txt"}}'
        elif i % 3 == 2:
            role, text = "tool", f"[tool result call_{i}] " + "data " * 24
        else:
            role, text = "user", f"turn {i}: " + "context " * 16
        blocks.append((i, role, text))
    return tuple(blocks)


def _settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flags: dict[str, object]
) -> Path:
    """Изолированный dynamic_config: env-ключи сняты, файл — единственный источник."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "dynamic_config.json"
    path.write_text(json.dumps(flags), encoding="utf-8")
    return path


def _cold_probe(strict: bool, reused: bool) -> ReuseProbe:
    """Холодный запрос инцидента: cid пуст, якоря resume нет."""
    return ReuseProbe(strict=strict, reused=reused, run_cid="", resume_base_idx=0)


def _legacy_prune(blocks: Sequence[object], tail: str, limit: int) -> str:
    """Детерминированный legacy-делегат: только хвост (head-pruning до фикса)."""
    rendered = [str(b[2]) for b in blocks]  # type: ignore[index]
    return "\n\n".join(rendered[-1:] + ([tail] if tail else []))


def _build_prompt(config_path: Path) -> tuple[str, object, dict[str, object]]:
    """Реальная компакция 845 блоков в request scope; prompt, collector и wire внутри scope."""
    request = CompactionAdapterRequest(
        blocks=_incident_blocks(), tail_block="", limit_bytes=CAP_BYTES,
        enabled=True, legacy_prune=_legacy_prune, config_path=config_path,
    )
    with begin_request_scope() as collector:
        prompt = render_or_compact_blocks(request)
        wire = usage_payload({}, _SUPPRESSED)
    return prompt, collector, wire


def test_incident_defaults_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings(monkeypatch, tmp_path, {})
    settings = read_loss_contract_settings(config_path=path)
    assert settings.strict_cold_rotation is True
    assert settings.loss_receipt_enabled is True


def test_two_cold_requests_never_reuse_live_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AD-001: оба холодных запроса идут в одноразовый spawn, слот не переиспользуется."""
    path = _settings(monkeypatch, tmp_path, {})
    strict = read_loss_contract_settings(config_path=path).strict_cold_rotation
    binding: SlotBinding | None = None
    verdicts: list[SlotReuseVerdict] = []
    for request_index in range(COLD_REQUESTS):
        probe = _cold_probe(strict, reused=binding is not None)
        verdict = decide_slot_reuse(probe, binding)
        verdicts.append(verdict)
        if verdict.evicts_slot:
            binding = None  # desync-eviction: привязка сброшена, one-shot cold spawn
        else:
            binding = (binding or SlotBinding()).after_turn("")
    assert verdicts == [SlotReuseVerdict.FRESH, SlotReuseVerdict.ROTATE_COLD]
    assert verdicts[1].evicts_slot is True


def test_rotated_cold_spawn_delivers_accounted_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """После ротации новый spawn получает историю; квитанция сохраняет закон сохранения."""
    path = _settings(monkeypatch, tmp_path, {})
    prompt, collector, wire = _build_prompt(path)
    receipt = collector.merged()
    assert receipt is not None and receipt.truncated is True
    assert receipt.original_messages == MESSAGES
    assert receipt.dropped_messages + receipt.digested_messages > 0
    assert receipt.effective_messages + receipt.digested_messages + receipt.dropped_messages == MESSAGES
    assert receipt.configured_prompt_cap_bytes == CAP_BYTES
    assert json_text_bytes(prompt) <= CAP_BYTES
    assert _incident_blocks()[-1][2] in prompt  # хвост (актуальный ход) дошёл до модели
    assert wire["prompt_tokens"] == 0 and wire["x_bridge_loss"] == receipt.to_wire()


def test_kill_switches_off_reproduce_silent_split_brain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Старый отказ: reuse живого слота холодным запросом + обрезка без квитанции."""
    path = _settings(
        monkeypatch, tmp_path,
        {"strict_cold_rotation": False, "loss_receipt_enabled": False},
    )
    settings = read_loss_contract_settings(config_path=path)
    assert settings.strict_cold_rotation is False and settings.loss_receipt_enabled is False
    binding = SlotBinding().after_turn("")  # слот остался жив после первого хода
    verdict = decide_slot_reuse(_cold_probe(settings.strict_cold_rotation, True), binding)
    assert verdict is SlotReuseVerdict.REUSE and verdict.evicts_slot is False
    prompt, collector, wire = _build_prompt(path)
    full = "\n\n".join(block[2] for block in _incident_blocks())
    assert json_text_bytes(prompt) < json_text_bytes(full)  # потеря реально произошла
    assert collector.merged() is None  # но квитанция не записана — silent loss
    assert wire == {}  # usage подавлен и без x_bridge_loss


def test_receipt_flag_alone_makes_loss_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Независимость kill-switchей: receipt включён — потеря видна даже при legacy-reuse."""
    path = _settings(
        monkeypatch, tmp_path,
        {"strict_cold_rotation": False, "loss_receipt_enabled": True},
    )
    settings = read_loss_contract_settings(config_path=path)
    verdict = decide_slot_reuse(_cold_probe(settings.strict_cold_rotation, True), SlotBinding().after_turn(""))
    assert verdict is SlotReuseVerdict.REUSE
    _, collector, wire = _build_prompt(path)
    receipt = collector.merged()
    assert receipt is not None and receipt.truncated is True
    assert receipt.original_messages == MESSAGES
    assert wire["x_bridge_loss"] == receipt.to_wire()


def test_guard_window_for_845_messages_keeps_anchor_and_active_group() -> None:
    """AD-011: 845 msgs -> WINDOW (не UNFIT): якорь и финальная группа целы, середина dropped."""
    blocks = tuple(PromptBlock(i, role, text) for i, role, text in _incident_blocks())
    decision = select_bounded_window(blocks, guard_bytes=32768)
    assert decision.verdict is GuardVerdict.WINDOW
    assert decision.dropped_messages > 0
    assert decision.window[0] == blocks[0]
    assert decision.window[-1] == blocks[-1]
    assert len(decision.window) + decision.dropped_messages == MESSAGES


def test_unfit_active_group_builds_400_receipt() -> None:
    """AD-010: якорь+актив не помещаются под гард -> UNFIT и тело 400 с квитанцией."""
    blocks = (
        PromptBlock(0, "user", "A" * 5000),
        PromptBlock(1, "assistant", '[tool call read] {"file_path": "/tmp/x"}'),
        PromptBlock(2, "tool", "B" * 5000),
    )
    decision = select_bounded_window(blocks, guard_bytes=4096)
    assert decision.verdict is GuardVerdict.UNFIT
    error = ClientCompactionRequired(decision.input_bytes, 4096, CAP_BYTES, len(blocks))
    body = error.body["error"]
    assert body["code"] == "context_length_exceeded"
    assert body["x_reason"] == "client_compaction_required"
    receipt = body["x_bridge_loss"]
    assert receipt["truncated"] is True and receipt["fallback_reason"] == "input_guard"
    assert receipt["dropped_messages"] == len(blocks)

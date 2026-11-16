"""Общий координатор terminal done и свежий fail-closed переключатель recovery."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, cast

import core.stream_interruption_recovery as recovery
import core.turn_outcome_policy as causal

_FLAG = "BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED"
_FALSE = ("0", "false", "no", "off")
_TRUE = ("1", "true", "yes", "on")

@dataclass(frozen=True)
class RecoveryAliases:
    """Дополнительные имена флагов транспорта: ядро остаётся вендор-нейтральным."""
    switch_vars: tuple[str, ...] = ()

def _flag_values(values: Mapping[str, str], names: tuple[str, ...]) -> tuple[str, ...]:
    """Нормализовать значения всех объявленных имён флагов и записать в регистр."""
    return tuple(values.get(name, "").strip().lower() for name in names)

def _config_value(data: object) -> bool | None:
    """Отличить отсутствие ключей от явного opt-in и запретов."""
    if not isinstance(data, dict):
        return False
    flags = cast(dict[str, object], data)
    present = tuple(flags[key] for key in (_FLAG, "causal_turn_recovery_enabled", "causal_recovery_enabled") if key in flags)
    return all(value is True for value in present) if present else None

def _read_config_flag(path: Path, max_bytes: int) -> bool | None:
    """Отсутствие opt-in нейтрально, некорректный источник запрещает recovery."""
    try:
        # NONBLOCK не меняет regular file, но позволяет отвергнуть FIFO без зависания.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        return False
    try:
        try:
            if (os.fstat(fd).st_mode & 0o170000) != 0o100000:
                return False
            raw = os.read(fd, max_bytes + 1)
        finally:
            os.close(fd)
        if len(raw) > max_bytes:
            return False
        return _config_value(cast(object, json.loads(raw.decode("utf-8"))))
    except (OSError, ValueError, RecursionError):
        return False

def _recovery_config_flags(local_path: Path | None, max_bytes: int, values: Mapping[str, str], global_path: Path | None) -> tuple[bool | None, ...]:
    """Прочитать общий и локальный источники без обхода локального вето."""
    override = values.get("BRIDGE_DYNAMIC_CONFIG_PATH", "").strip()
    default = global_path if global_path is not None else Path.home() / ".config/cli-agent-bridge/dynamic_config.json"
    paths = (Path(override), local_path) if override else (default, local_path)
    return tuple(_read_config_flag(path, max_bytes) for path in paths if path is not None)

def read_recovery_switch(
    local_path: Path | None, max_bytes: int, env: Mapping[str, str] | None = None,
    global_path: Path | None = None, aliases: RecoveryAliases | None = None,
) -> bool:
    """Прозрачный opt-in: любой включённый источник включает, любой запрет — вето."""
    values = os.environ if env is None else env
    extra = aliases if aliases is not None else RecoveryAliases()
    switches = _flag_values(values, (_FLAG, *extra.switch_vars))
    if any(value not in ("", *_TRUE) for value in switches):
        return False
    if type(max_bytes) is not int or max_bytes <= 0:
        return False
    flags = _recovery_config_flags(local_path, max_bytes, values, global_path)
    return False not in flags and (True in flags or any(value in _TRUE for value in switches))

@dataclass(frozen=True)
class DoneRequest:
    """Неизменённый legacy-контракт W2: Any обязателен только на этой границе."""
    payload: tuple[int, str, dict[str, Any] | None]  # pyright: ignore[reportExplicitAny]
    result_ev: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    errors: tuple[str, str]

@dataclass(frozen=True)
class DonePorts:
    """Legacy closures W2 с Any, без владения их mutable буферами."""
    state: Callable[..., Any]  # pyright: ignore[reportExplicitAny]
    add_content: Callable[[str], Any]  # pyright: ignore[reportExplicitAny]
    deliver: Callable[[list[Any]], Any]  # pyright: ignore[reportExplicitAny]
    is_client_gone: Callable[[], bool]
    turn_complete: Any = None  # pyright: ignore[reportExplicitAny]

@dataclass(frozen=True)
class DoneTextFacts:
    """Полные ошибки до усечения и уже доставленный текст."""
    final_text: str
    emitted_text: str
    result_error: str
    cleared_error: str

@dataclass(frozen=True)
class DoneResultFacts:
    """Наблюдённые transport status и фактический выход процесса."""
    result_status: str
    rc: int | None
    process_exited: bool
    attempt: int
    has_fatal_error: bool = False

@dataclass(frozen=True)
class DoneDeliveryFacts:
    """Порты reconcile и признаки доставки после drain."""
    content_streaming: bool
    pieces_empty: bool
    reconcile: Callable[[str], str]
    fallback_deliver: bool | Callable[[], bool]

@dataclass(frozen=True)
class DoneDrainFacts:
    """Complete доказывается только после остановки и join производителя."""
    outcome: str = ""
    producer_stopped: bool = False

@dataclass(frozen=True)
class DoneRecoveryFacts:
    """Снимок текущего хвоста без истории завершённых инструментов."""
    self_heal_enabled: bool
    tail: object
    drain_meta: DoneDrainFacts
    tool_status: str

@dataclass(frozen=True)
class DoneSnapshot:
    """Транспорт собирает все группы только после bounded drain."""
    text: DoneTextFacts
    result: DoneResultFacts
    delivery: DoneDeliveryFacts
    recovery: DoneRecoveryFacts

@dataclass(frozen=True)
class DoneConfig:
    """Все эксплуатационные бюджеты задаёт вызывающая сторона."""
    local_path: Path | None
    max_bytes: int
    content_streaming: bool = False
    usage_enabled: bool = False
    aliases: RecoveryAliases | None = None

@dataclass(frozen=True)
class DoneRuntimePorts:
    """Drain уже ограничен бюджетом транспорта; stderr wait также опционален."""
    snapshot: Callable[[], DoneSnapshot]
    drain: Callable[[], list[object]] | None = None
    stderr: Callable[[], str] | None = None

def _causal_input(snapshot: DoneSnapshot, enabled: bool, error: str) -> causal.CausalOutcomeInput:
    """Собирает единственный набор каузальных доказательств без усечения строк."""
    proof = recovery.tail_causal_facts(snapshot.recovery.tail)
    result, meta = snapshot.result, snapshot.recovery.drain_meta
    complete = meta.outcome == "complete"
    return causal.CausalOutcomeInput(
        causal.CausalRecoveryConfig(snapshot.recovery.self_heal_enabled, enabled, result.attempt,
                                    bool(getattr(snapshot.recovery.tail, "had_safety_error", False)) or causal.is_fatal_safety_error(error)),
        causal.CausalErrorFacts(proof.error, proof.error_from_structured_record,
                                result.result_status, causal.error_identity_digest(error)),
        proof.completion,
        causal.CausalTerminalFacts(
            causal.CausalDrainFacts(complete, complete and meta.producer_stopped, meta.producer_stopped),
            causal.CausalProcessFacts(result.process_exited, result.rc, result.has_fatal_error),
            snapshot.recovery.tool_status, proof.has_late_error_or_open_step),
    )

def _resolve_done(
    snapshot: DoneSnapshot, enabled: bool, payload_rc: int,
) -> recovery.TurnOutcomeResolution:
    """Единое решение выдачи и снятия ошибки принимается до любого reconcile."""
    text, result = snapshot.text, snapshot.result
    drain_meta = snapshot.recovery.drain_meta
    status = result.result_status.upper()
    error = recovery.settle_error(text.result_error, text.cleared_error, status)
    facts = _causal_input(snapshot, enabled, error)
    return recovery.resolve_done_turn_outcome(
        rc=result.rc if type(result.rc) is int else payload_rc,
        result_error=error, result_status=status,
        final_text=_final_text(snapshot), emitted_text=text.emitted_text,
        self_heal_enabled=snapshot.recovery.self_heal_enabled, causal_input=facts,
        completion_done_without_tools=facts.completion.completion_done_without_tools,
        last_completion_seq=facts.completion.last_completion_seq,
        last_error_seq=facts.error.identity.seq,
        drain_complete=bool(drain_meta.outcome) and drain_meta.outcome != "timeout" and drain_meta.producer_stopped,
        had_transient_error=bool(getattr(snapshot.recovery.tail, "had_transient_error", False) or text.cleared_error),
        has_unclosed_tool_call=snapshot.recovery.tool_status != "closed",
    )

def _final_text(snapshot: DoneSnapshot) -> str:
    """Выбирает legacy planner fallback только при ошибке и доказанном DONE."""
    text = snapshot.text
    error = recovery.settle_error(text.result_error, text.cleared_error, snapshot.result.result_status.upper())
    if not error:
        return text.final_text
    tail = snapshot.recovery.tail
    return (text.final_text or str(getattr(tail, "final_planner_content", ""))) if getattr(tail, "final_planner", False) else ""

def _emit_result(snapshot: DoneSnapshot, ports: DonePorts) -> None:
    """Досылает только заранее разрешённый финал, сохраняя Markdown-разделитель."""
    text, delivery = snapshot.text, snapshot.delivery
    final_text = _final_text(snapshot)
    if delivery.content_streaming:
        delta = delivery.reconcile(final_text)
        if delta:
            ports.add_content(delta)
        else:
            fallback = delivery.fallback_deliver
            diverged = fallback() if callable(fallback) else fallback
            if final_text and diverged:
                emitted = text.emitted_text
                separator = (
                    "" if not emitted or emitted.endswith("\n\n")
                    else "\n" if emitted.endswith("\n") else "\n\n"
                )
                ports.add_content(separator + final_text)
    elif delivery.pieces_empty and final_text:
        ports.add_content(final_text)

def _legacy_done(
    request: DoneRequest, ports: DonePorts, snapshot: DoneSnapshot,
    resolution: recovery.TurnOutcomeResolution, runtime: DoneRuntimePorts,
) -> object:
    """Сохраняет порядок legacy final, client_gone и stderr/error fallback."""
    if resolution.final:
        return cast(object, ports.state(resolution.state, resolution.rc, resolution.error))
    if ports.is_client_gone():
        return cast(object, ports.state("client_gone", 1))
    err = runtime.stderr().strip() if runtime.stderr is not None else ""
    rc = snapshot.result.rc if type(snapshot.result.rc) is int else request.payload[0]
    if rc != 0 and (snapshot.result.result_status.upper() == "ERROR" or snapshot.delivery.pieces_empty):
        result = request.result_ev or request.payload[2] or {}
        message = str(result.get("error") or "") or err
        return cast(object, ports.state("agy_error", rc, message[:500]))
    return cast(object, ports.state("done", rc, err))

def finalize_done(
    request: DoneRequest, ports: DonePorts, runtime: DoneRuntimePorts,
    config: DoneConfig, log: Callable[[str], object],
) -> object:
    """Drain → свежий kill-switch → решение → разрешённая выдача → terminal state."""
    if (config.content_streaming or config.usage_enabled) and runtime.drain is not None:
        ports.deliver(runtime.drain())
    snapshot = runtime.snapshot()
    enabled = read_recovery_switch(config.local_path, config.max_bytes, aliases=config.aliases)
    resolution = _resolve_done(snapshot, enabled, request.payload[0])
    if resolution.state == "done":
        _emit_result(snapshot, ports)
    if resolution.self_healed and resolution.reason == "causal_echo_recovered":
        proof = recovery.tail_causal_facts(snapshot.recovery.tail)
        _ = log(json.dumps(dict(reason=resolution.reason, last_error_seq=proof.error.seq,
                            last_completion_seq=proof.completion.last_completion_seq, rc=snapshot.result.rc)))
        return cast(object, ports.state("done", 0, ""))
    return _legacy_done(request, ports, snapshot, resolution, runtime)

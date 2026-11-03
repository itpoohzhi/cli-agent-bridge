#!/usr/bin/env python3
"""Исполняемый PoC QA-гейта: replay, handoff, canary и опциональный живой SSE.

Консолидированный контракт этого модуля нормативен для данного PoC.
G1 — компонентный replay, не E2E. Мутации G3 изолированы процессом, не
песочницей; импорт bridge может иметь побочные эффекты. Tiers и новые состояния
FSM не реализованы. Live запускается только явно переданным --live-hub;
разрешение владельца должен обеспечить вызывающий оркестратор.

SHA-256 — каноническая контрольная сумма, НЕ подпись и не доказательство
доверенного происхождения. Оркестратор обязан сам исполнить предопределённый
полный suite, проверить его результат, затем безусловно вызвать
verify_proof_contract для маршрута qa_gate_required. Проверка текста handoff
не заменяет исполнения тестов. G2 без --handoff — только self-test валидатора.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TESTS = frozenset(
    {
        "tests/test_qa_product_gate.py",
        "tests/test_agy_bridge_resilience.py",
        "tests/test_stream_formatting_and_subagents.py",
    }
)
GLUE_PATTERN = re.compile(r"[а-яёa-z]\.[А-ЯЁA-Z]")
PREFIX = "[гейт оркестрации: активен | роль: orchestrator]\n\n"
_bridge_module: ModuleType | None = None
_MISSING = object()
Result = dict[str, Any]


def _positive_env(name: str, default: float) -> float:
    value = float(os.environ.get(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: требуется конечное положительное число")
    return value


@dataclass(frozen=True)
class GateConfig:
    """Окружение читается при запуске, не при импорте."""

    min_steps: int = 30
    live_timeout_s: float = 120.0
    live_total_timeout_s: float = 300.0
    max_response_bytes: int = 4 * 1024 * 1024
    max_sse_line_bytes: int = 256 * 1024
    log_tail_bytes: int = 64 * 1024
    parser_chunk_chars: int = 7
    git_timeout_s: float = 10.0
    read_chunk_bytes: int = 8192
    min_canary_total: int = 5
    log_error_pattern: str = r"Traceback|\b5\d\d\b|content-divergence"
    model: str = ""
    log_path: Path = REPO_ROOT / "logs" / "bridge.err"
    worktree_fingerprint: str = ""

    @classmethod
    def from_env(cls) -> GateConfig:
        def integer(name: str, default: int) -> int:
            value = _positive_env(name, default)
            if not value.is_integer():
                raise ValueError(f"{name}: требуется целое число")
            return int(value)

        steps = integer("QA_GATE_MIN_STEPS", 30)
        if steps < 30:
            raise ValueError("QA_GATE_MIN_STEPS должен быть >= 30")
        return cls(
            min_steps=steps,
            live_timeout_s=_positive_env("QA_GATE_LIVE_TIMEOUT_S", 120.0),
            live_total_timeout_s=_positive_env("QA_GATE_LIVE_TOTAL_TIMEOUT_S", 300.0),
            max_response_bytes=integer("QA_GATE_MAX_RESPONSE_BYTES", 4 * 1024 * 1024),
            max_sse_line_bytes=integer("QA_GATE_MAX_SSE_LINE_BYTES", 256 * 1024),
            log_tail_bytes=integer("QA_GATE_LOG_TAIL_BYTES", 64 * 1024),
            parser_chunk_chars=integer("QA_GATE_PARSER_CHUNK_CHARS", 7),
            git_timeout_s=_positive_env("QA_GATE_GIT_TIMEOUT_S", 10.0),
            read_chunk_bytes=integer("QA_GATE_READ_CHUNK_BYTES", 8192),
            min_canary_total=integer("QA_GATE_MIN_CANARY_TOTAL", 5),
            log_error_pattern=os.environ.get(
                "QA_GATE_LOG_ERROR_PATTERN", cls.log_error_pattern
            ).strip()
            or cls.log_error_pattern,
            model=os.environ.get("QA_GATE_MODEL", "").strip(),
            log_path=Path(os.environ.get("QA_GATE_LOG_PATH", str(cls.log_path))),
            worktree_fingerprint=os.environ.get(
                "QA_GATE_WORKTREE_FINGERPRINT", ""
            ).strip(),
        )


def _api_key() -> str:
    """Не интерпретирует shell и не выполняет содержимое dotenv."""
    for name in ("QA_GATE_API_KEY", "BRIDGE_KEY"):
        if name in os.environ:
            return os.environ[name].strip()
    try:
        for line in (
            (Path.home() / ".dsh" / ".env").read_text(encoding="utf-8").splitlines()
        ):
            match = re.fullmatch(r"\s*(?:export\s+)?BRIDGE_KEY\s*=(.*)", line)
            if match:
                value = match.group(1).strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    return value[1:-1]
                return value.split(" #", 1)[0].strip()
    except (OSError, UnicodeError):
        pass
    return ""


def sanitize(value: str) -> str:
    """Маскирует типовые секреты перед попаданием в proof и stdout."""
    value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
    value = re.sub(
        r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        value,
    )
    for name in ("QA_GATE_API_KEY", "BRIDGE_KEY", "AGY_BRIDGE_KEY", "OPENAI_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def _safe_tree(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, dict):
        return {key: _safe_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_tree(item) for item in value]
    return value


def _result(checks: Mapping[str, bool], **evidence: Any) -> Result:
    return {
        "status": "PASS" if checks and all(checks.values()) else "FAIL",
        "checks": dict(checks),
        **evidence,
    }


def _checked(action: Callable[[], Result]) -> Result:
    try:
        return action()
    except Exception as exc:
        return _result(
            {"completed": False}, error=sanitize(f"{type(exc).__name__}: {exc}")
        )


def _bridge() -> ModuleType:
    global _bridge_module
    if _bridge_module is None:
        root = str(REPO_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        spec = importlib.util.spec_from_file_location(
            "_qa_product_gate_agy", REPO_ROOT / "bridges/agy-bridge/server.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("не удалось загрузить agy bridge")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(spec.name, None)
            raise
        _bridge_module = module
    return _bridge_module


def _new_run() -> Any:
    """Настоящий Run без запуска внешнего CLI."""
    srv = _bridge()
    run = object.__new__(srv.Run)
    run._emit_lock = threading.Lock()
    run.q = queue.Queue()
    run.drain_closed = False
    run._done_put = False
    run._reasoning_bytes = 0
    run._cap_logged = False
    run.turn_id = "qa-product-gate"
    run.run_cid = "qa-product-gate"
    run._tail = SimpleNamespace(cid=run.run_cid)
    run._arbiter = srv._ContentArbiter(run.turn_id)
    run._last_step_index = None
    run._content_emitted_wire = ""
    run._preambles_emitted = set()
    return run


def _drain(run: Any) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    while True:
        try:
            events.append(run.q.get_nowait())
        except queue.Empty:
            return events


def _tail(run: Any, isolate: bool) -> Any:
    srv = _bridge()
    plan = srv._TurnPlan()
    plan.mode = "OFF"
    plan.base_idx = 0
    plan.offset = 0
    tail = srv._TranscriptTail(
        emit=run._emit_reasoning,
        stop_event=threading.Event(),
        done_event=threading.Event(),
        resumed=False,
        plan=plan,
        turn_id=run.turn_id,
        emit_content=run._offer_transcript,
        isolate_tool_preambles=isolate,
        preambles_emitted=run._preambles_emitted,
        run_ref=run,
    )
    tail.cid = run.run_cid
    run._tail = tail
    return tail


def _record(tail: Any, idx: int, text: str, tools: bool = False) -> None:
    record: Result = {"type": "PLANNER_RESPONSE", "step_index": idx, "content": text}
    if tools:
        record["tool_calls"] = [{"name": "invoke_subagent", "args": {"step": idx}}]
    tail._emit_record(json.dumps(record, ensure_ascii=False).encode())


def _sse(events: list[tuple[str, Any]], timeout: str | None = None) -> list[Result]:
    """Настоящий SSE-сериализатор и graceful-finalizer, подменённый транспорт."""
    srv = _bridge()
    handler = object.__new__(srv.Handler)
    frames: list[str] = []
    handler._emit = lambda data: frames.append(data) or True
    handler.send_response = lambda *_args: None
    handler.send_header = lambda *_args: None
    handler.end_headers = lambda: None

    def run_once(
        ctx: Result, on_text: Any, _tool: Any, on_reasoning: Any, _keep: Any
    ) -> Result:
        for kind, value in events:
            if kind == "text":
                on_text(value)
            elif kind == "reasoning":
                on_reasoning(value)
        return {
            "state": timeout or "done",
            "rc": 124 if timeout else 0,
            "text": "".join(str(value) for kind, value in events if kind == "text"),
            "err": "",
            "usage": {},
            "conversation_id": "qa-product-gate",
            "retained_events": [("text", "\n\nХвост graceful drain.")]
            if timeout
            else [],
        }

    handler._run_once = run_once
    original_flag = srv._new_flag
    with patch.object(
        srv,
        "_new_flag",
        side_effect=lambda name, *args: (
            True
            if name
            in ("graceful_timeout_on_partial", "AGY_BRIDGE_STREAM_RESILIENCE_ENABLED")
            else original_flag(name, *args)
        ),
    ):
        handler._serve_sse({"model": "qa-replay"})
    return _parse_sse(("".join(frames)).splitlines(keepends=True), GateConfig())


def _parse_sse(
    lines: Iterable[bytes | str],
    config: GateConfig,
    *,
    stop_at_done: bool = False,
    deadline: float | None = None,
) -> list[Result]:
    """Проверяет framing, terminal stop, DONE, ошибки и непустой content."""
    frames: list[Result] = []
    data: list[str] = []
    done = False
    terminal = False
    size = 0
    if deadline is None:
        deadline = time.monotonic() + config.live_total_timeout_s
    for raw in lines:
        if time.monotonic() >= deadline:
            raise ValueError("превышен полный бюджет SSE")
        line_bytes = raw if isinstance(raw, bytes) else raw.encode()
        size += len(line_bytes)
        if (
            size > config.max_response_bytes
            or len(line_bytes) > config.max_sse_line_bytes
        ):
            raise ValueError("превышен лимит SSE")
        line = line_bytes.decode("utf-8").rstrip("\r\n")
        if line.startswith(":"):
            continue
        if line:
            if done or not line.startswith("data:"):
                raise ValueError("невалидное SSE framing")
            data.append(line[5:].lstrip(" "))
            continue
        if not data:
            continue
        payload = "\n".join(data)
        data.clear()
        if payload == "[DONE]":
            if done or not terminal:
                raise ValueError("DONE без terminal stop")
            done = True
            if stop_at_done:
                break
            continue
        frame = json.loads(payload)
        if not isinstance(frame, dict) or frame.get("error"):
            raise ValueError("SSE error frame")
        choices = frame.get("choices")
        if not isinstance(choices, list):
            raise ValueError("нет choices в SSE")
        for choice in choices:
            if not isinstance(choice, dict) or not isinstance(
                choice.get("delta"), dict
            ):
                raise ValueError("невалидная choice/delta")
            delta = choice["delta"]
            if any(
                name in delta and not isinstance(delta[name], str)
                for name in ("content", "reasoning_content")
            ):
                raise ValueError("нестроковая content/reasoning_content")
            if terminal and any(delta.values()):
                raise ValueError("полезная дельта после terminal")
            reason = choice.get("finish_reason")
            if reason is not None:
                if reason != "stop":
                    raise ValueError(f"finish_reason={reason!r}, требуется stop")
                terminal = True
        frames.append(frame)
    if data or not done or not terminal:
        raise ValueError("оборванный SSE: нет terminal stop / DONE")
    if not _channel(frames, "content").strip():
        raise ValueError("пустой assembled content")
    return frames


def _channel(frames: list[Result], name: str) -> str:
    return "".join(
        str(choice["delta"].get(name) or "")
        for frame in frames
        for choice in frame["choices"]
    )


def _wave_prefix(config: GateConfig) -> Result:
    run = _new_run()
    expected: list[str] = []
    for idx in range(config.min_steps):
        mark = ("[ ]", "[>]", "[x]")[idx % 3]
        text = (
            PREFIX + f"- P0 · [x] Канон прочитан.\n- P1 · {mark} Проверка {idx + 1}: "
        )
        text += "сверяю полный вывод тестов, артефакты и результат делегирования."
        if idx == config.min_steps - 1:
            text += "\n\nИТОГ: все шаги сохранены, финальный ответ доставлен владельцу."
        source = "stdout" if idx % 2 == 0 else "transcript"
        other = "transcript" if source == "stdout" else "stdout"
        run.offer_content(source, idx, PREFIX[:27])
        run.offer_content(source, idx, text)
        run.offer_content(other, idx, text)
        expected.append(text)
    content = _channel(_sse(_drain(run)), "content")
    return _result(
        {
            "all_steps_exact": content == "\n\n".join(expected),
            "no_false_freeze": not any(
                step.frozen for step in run._arbiter.by_key.values()
            ),
            "zero_divergences": run._arbiter.divergences == 0,
            "no_overflow": not run._arbiter.overflow,
            "final_preserved": content.endswith(expected[-1]),
        },
        steps=config.min_steps,
        divergences=run._arbiter.divergences,
    )


def _wave_boundary() -> Result:
    run = _new_run()
    tail = _tail(run, False)
    texts = [
        "План сформирован, закончена проверка данных.",
        "Проверяю логи и результаты фоновых исполнителей.",
        "Validated the final report.",
        "Checking the evidence before delivery.",
    ]
    for idx, text in enumerate(texts):
        _record(tail, idx, text)
    content = _channel(_sse(_drain(run)), "content")
    return _result(
        {
            "no_glue": GLUE_PATTERN.search(content) is None,
            "exact_boundaries": content == "\n\n".join(texts),
        }
    )


def _wave_think() -> Result:
    run = _new_run()
    tail = _tail(run, True)
    preambles = [
        "Запускаю Coder: собрать regression и проверить контракт.",
        "Ожидаю Reviewer: сверить полный прогон с критериями приёмки.",
        "Проверяю артефакты launch_seat.py и непрерывность родительского потока.",
    ]
    intermediate: list[tuple[str, Any]] = []
    for idx, text in enumerate(preambles, 1):
        _record(tail, idx, text, tools=True)
        _record(tail, idx, text, tools=True)
        intermediate.extend(_drain(run))
    final = "Финальный ответ: полный отчёт с доказательствами проверки."
    _record(tail, 4, final)
    frames = _sse(intermediate + _drain(run))
    reasoning = _channel(frames, "reasoning_content")
    return _result(
        {
            "no_intermediate_content": not any(
                kind == "text" and text for kind, text in intermediate
            ),
            "all_preambles_in_reasoning": all(
                reasoning.count(text) == 1 for text in preambles
            ),
            "final_only_content": _channel(frames, "content") == final,
        }
    )


def _wave_graceful() -> Result:
    checks: dict[str, bool] = {}
    for state in ("timeout", "idle_timeout"):
        content = _channel(
            _sse([("text", "Частичный полезный ответ.")], state), "content"
        )
        checks[state] = (
            "Частичный полезный ответ." in content
            and "Хвост graceful drain." in content
        )
    return _result(checks)


def _wave_tools(config: GateConfig) -> Result:
    _bridge()
    from core.tool_emulation import StreamNormalizer, sanitize_tool_calls_list

    open_tag = "<tool_" + "call>"
    close_tag = "</tool_" + "call>"
    cases = [
        (
            open_tag + '{"name":"read_file","arguments":{"path":"a"}}}}' + close_tag,
            1,
        ),
        (
            open_tag + '{"name":"read_file","arguments":""}' + close_tag,
            0,
        ),
        (
            "Пример: `" + open_tag + '{"name":"example"}' + close_tag + "` — это код.",
            0,
        ),
        (
            "".join(
                open_tag
                + '{"name":"read_file","arguments":{"path":"'
                + p
                + '"}}'
                + close_tag
                for p in ("a", "b", "c")
            ),
            3,
        ),
    ]
    checks: dict[str, bool] = {}
    for idx, (raw, count) in enumerate(cases):
        parser = StreamNormalizer(strict_live=False)
        for offset in range(0, len(raw), config.parser_chunk_chars):
            parser.feed(raw[offset : offset + config.parser_chunk_chars])
        parser.finish()
        calls = sanitize_tool_calls_list(
            [dict(call, index=99) for call in parser.tool_calls]
        )
        checks[f"case_{idx}_count"] = len(calls) == count
        checks[f"case_{idx}_indices"] = [call["index"] for call in calls] == list(
            range(count)
        )
        if idx == 0 and calls:
            checks["recovered_braces_arguments"] = calls[0]["arguments"] == {
                "path": "a"
            }
        if idx == 2:
            checks["inline_code_preserved"] = parser.content == raw
    schemas = {
        "read_file": {
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "optional": {"type": "string"},
                    "command": {"type": "string"},
                },
                "required": ["path"],
            }
        }
    }
    cleaned = sanitize_tool_calls_list(
        [
            {
                "name": "read_file",
                "arguments": {"path": "a", "optional": "", "command": ""},
            }
        ],
        schemas,
    )
    checks["empty_optional_sanitized_payload_preserved"] = cleaned[0]["arguments"] == {
        "path": "a",
        "command": "",
    }
    return _result(checks)


def run_incident_replay_suite(config: GateConfig | None = None) -> Result:
    """G1: каждый incident независимо даёт PASS/FAIL с собственным оракулом."""
    config = config or GateConfig.from_env()
    waves = {
        "wave_1a_prefix": _checked(lambda: _wave_prefix(config)),
        "wave_1b_boundary": _checked(_wave_boundary),
        "wave_1c_think": _checked(_wave_think),
        "wave_3_graceful": _checked(_wave_graceful),
        "wave_4_tools": _checked(lambda: _wave_tools(config)),
    }
    return _result(
        {name: value["status"] == "PASS" for name, value in waves.items()},
        incidents=waves,
    )


def validate_handoff_commands(
    payload: Any,
    *,
    final_readiness: bool = True,
    allow_gate_subset: bool = False,
) -> list[str]:
    """Статическая дополнительная проверка, не свидетельство исполнения тестов.

    allow_gate_subset явно включает минимальный QA-набор вместо полного suite.
    RED/diagnostic никогда не обеспечивают final coverage.
    """
    if not isinstance(payload, dict):
        return ["handoff должен быть JSON object"]
    commands = payload.get("verification_commands")
    if not isinstance(commands, list) or not commands:
        return ["verification_commands должен быть непустым массивом"]
    errors: list[str] = []
    full_coverage = False
    nonexecuting = {
        "--setup-only",
        "--setup-plan",
        "--setup-show",
        "--fixtures",
        "--fixtures-per-test",
        "--markers",
        "--version",
        "--help",
        "-h",
        "--cache-show",
        "-V",
        "--collect-only",
        "--co",
    }
    selective_prefixes = (
        "-k",
        "-m",
        "-o",
        "-c",
        "--override-ini",
        "--deselect",
        "--ignore",
        "--lf",
        "--last-failed",
        "--stepwise",
        "--pyargs",
    )
    safe_flags = {
        "-q",
        "-qq",
        "-v",
        "-vv",
        "-vvv",
        "-s",
        "-x",
        "--quiet",
        "--verbose",
        "--disable-warnings",
        "--strict-markers",
        "--strict-config",
        "--showlocals",
    }
    for idx, item in enumerate(commands):
        label = f"verification_commands[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: требуется object")
            continue
        purpose = item.get("purpose", "final")
        code = item.get("exit_code")
        if purpose not in ("final", "red_repro", "diagnostic"):
            errors.append(f"{label}.purpose: неизвестное назначение")
        if purpose == "final" and (type(code) is not int or code != 0):
            errors.append(f"{label}.exit_code должен быть целым 0 для final")
        elif purpose == "red_repro" and (type(code) is not int or code <= 0):
            errors.append(f"{label}.exit_code должен быть целым > 0 для red_repro")
        elif purpose == "diagnostic" and type(code) is not int:
            errors.append(f"{label}.exit_code должен быть целым для diagnostic")
        command = item.get("command")
        if not isinstance(command, str) or not command.strip():
            errors.append(f"{label}.command отсутствует")
            continue
        try:
            tokens = shlex.split(command)
        except ValueError:
            errors.append(f"{label}: невалидная командная строка")
            continue
        if any(char in command for char in (";", "|", "&", "`", "$", "\n", ">", "<")):
            errors.append(f"{label}: shell composition не допускается")
            continue
        if tokens and Path(tokens[0]).name == "run-guarded" and "--" in tokens:
            tokens = tokens[tokens.index("--") + 1 :]
        if tokens[:2] == ["uv", "run"]:
            tokens = tokens[2:]
        pytest_at = None
        if tokens and Path(tokens[0]).name in ("pytest", "pytest.exe"):
            pytest_at = 0
        elif (
            len(tokens) >= 3
            and re.fullmatch(r"python(?:\d+(?:\.\d+)?)?", Path(tokens[0]).name)
            and tokens[1:3] == ["-m", "pytest"]
        ):
            pytest_at = 2
        if pytest_at is None:
            continue
        args = tokens[pytest_at + 1 :]
        no_execution = any(t.split("=", 1)[0] in nonexecuting for t in args)
        if no_execution:
            errors.append(f"{label}: pytest без исполнения тестов запрещён")
        selective = any(t.startswith(selective_prefixes) for t in args)
        # Консервативный allowlist: неизвестный option не доказывает full suite.
        # Это также закрывает сокращения длинных options и plugin options.
        unknown_flags = any(t.startswith("-") and t not in safe_flags for t in args)
        targets = {
            t.removeprefix("./").rstrip("/") for t in args if not t.startswith("-")
        }
        repository_suite = not targets or targets in ({""}, {"tests"}, {"."})
        gate_subset = (
            allow_gate_subset
            and REQUIRED_TESTS.issubset(targets)
            and all(t in REQUIRED_TESTS for t in targets)
        )
        covered = (
            not no_execution
            and not selective
            and not unknown_flags
            and (repository_suite or gate_subset)
        )
        if final_readiness and purpose == "final" and not covered:
            errors.append(f"{label}: selective pytest без полного покрытия")
        full_coverage |= (
            covered and purpose == "final" and type(code) is int and code == 0
        )
    if final_readiness and not full_coverage:
        errors.append("нет успешного полного pytest gate")
    return errors


def _reference_handoff() -> Result:
    return {
        "verification_commands": [
            {"command": "pytest tests/ -v", "exit_code": 0, "purpose": "final"}
        ]
    }


def run_sdlc_integrity_check(payload: Any = _MISSING) -> Result:
    """G2: проверка handoff либо явно обозначенный self-test валидатора."""
    if payload is not _MISSING:
        errors = validate_handoff_commands(payload)
        return _result(
            {"valid_handoff": not errors}, scope="provided_handoff", errors=errors
        )
    errors = validate_handoff_commands(_reference_handoff())
    negative = {
        "verification_commands": [{"command": "pytest tests/ -q", "exit_code": 1}]
    }
    selective = {
        "verification_commands": [
            {"command": "pytest tests/ -k useful", "exit_code": 0}
        ]
    }
    single = {
        "verification_commands": [
            {"command": "pytest tests/test_qa_product_gate.py", "exit_code": 0}
        ]
    }
    return _result(
        {
            "reference_green": not errors,
            "nonzero_rejected": bool(validate_handoff_commands(negative)),
            "filter_rejected": bool(validate_handoff_commands(selective)),
            "single_file_rejected": bool(validate_handoff_commands(single)),
        },
        scope="validator_self_test",
        errors=errors,
    )


def run_canary_sensitivity_gate(config: GateConfig | None = None) -> Result:
    """G3: baseline → пять независимых дефектов → восстановление после каждого."""
    config = config or GateConfig.from_env()
    srv = _bridge()
    from core import tool_emulation

    baseline = (
        run_incident_replay_suite(config)["status"] == "PASS"
        and run_sdlc_integrity_check()["status"] == "PASS"
    )
    original_scan = srv._ContentArbiter._scan
    original_offer = srv.Run.offer_content
    original_tail_init = srv._TranscriptTail.__init__

    def unsafe_scan(
        self: Any, eq: Any, texts: Any, source: str, idx: Any, text: str
    ) -> Any:
        return original_scan(self, eq, texts, source, None, text)

    def leaky_tail(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["isolate_tool_preambles"] = False
        original_tail_init(self, *args, **kwargs)

    def glued_offer(self: Any, *args: Any, **kwargs: Any) -> bool:
        ok = original_offer(self, *args, **kwargs)
        for kind, value in _drain(self):
            self.q.put((kind, value.replace("\n\n", "") if kind == "text" else value))
        return ok

    def bypass_sanitizer(calls: Any, *_args: Any, **_kwargs: Any) -> Any:
        return calls

    bad_handoff = {
        "verification_commands": [{"command": "pytest tests/ -v", "exit_code": 1}]
    }
    canaries = [
        (
            "canary_1_prefix_alias_freeze",
            patch.object(srv._ContentArbiter, "_scan", unsafe_scan),
            lambda: _wave_prefix(config),
        ),
        (
            "canary_2_think_leak_to_content",
            patch.object(srv._TranscriptTail, "__init__", leaky_tail),
            _wave_think,
        ),
        (
            "canary_3_step_boundary_glue",
            patch.object(srv.Run, "offer_content", glued_offer),
            _wave_boundary,
        ),
        (
            "canary_4_handoff_nonzero_exit",
            patch.dict(
                _reference_handoff.__globals__,
                {"_reference_handoff": lambda: bad_handoff},
            ),
            run_sdlc_integrity_check,
        ),
        (
            "canary_5_tool_sanitizer_bypass",
            patch.object(tool_emulation, "sanitize_tool_calls_list", bypass_sanitizer),
            lambda: _wave_tools(config),
        ),
    ]
    results: list[Result] = []
    for name, mutation, oracle in canaries:
        before = _checked(oracle)
        with mutation:
            mutated = _checked(oracle)
        restored = _checked(oracle)
        killed = (
            before["status"] == "PASS"
            and mutated["status"] == "FAIL"
            and "error" not in mutated
        )
        results.append(
            {
                "name": name,
                "clean_green": before["status"] == "PASS",
                "killed": killed,
                "mutated": mutated,
                "post_restore_green": restored["status"] == "PASS",
            }
        )
    killed_count = sum(item["killed"] for item in results)
    restored_green = all(item["post_restore_green"] for item in results)
    return _result(
        {
            "baseline_green": baseline,
            "minimum_canaries_met": len(canaries) >= config.min_canary_total,
            "all_canaries_killed": killed_count == len(canaries),
            "post_restore_green": restored_green,
        },
        total=len(canaries),
        killed=killed_count,
        kill_rate=killed_count / len(canaries),
        post_restore_green=restored_green,
        canaries=results,
    )


def _log_snapshot(config: GateConfig) -> tuple[tuple[int, int] | None, int, bytes]:
    try:
        with config.log_path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            tail_size = min(stat.st_size, config.log_tail_bytes)
            stream.seek(stat.st_size - tail_size)
            return (
                (stat.st_dev, stat.st_ino),
                stat.st_size,
                stream.read(tail_size),
            )
    except OSError:
        return None, 0, b""


def _remaining_timeout(config: GateConfig, deadline: float) -> float:
    if time.monotonic() >= deadline:
        raise TimeoutError("превышен полный бюджет live probe")
    return min(config.live_timeout_s, max(0.05, deadline - time.monotonic()))


def _response_chunks(
    response: Any, config: GateConfig, deadline: float
) -> Iterable[bytes]:
    """read1 не ждёт заполнения всего буфера; бюджет обновляется перед чтением.

    Для HTTPResponse urllib используется socket timeout. Если транспорт не
    позволяет обновить timeout, строгая проверка завершается ошибкой.
    Это не sandbox и не гарантия прерывания системного DNS resolver.
    """
    read_any = False
    while True:
        timeout = _remaining_timeout(config, deadline)
        fp = getattr(response, "fp", None)
        raw = getattr(fp, "raw", None)
        sock = getattr(raw, "_sock", None)
        if sock is None:
            if read_any and getattr(response, "fp", None) is None:
                return
            raise ValueError("транспорт не поддерживает ограничение чтения")
        sock.settimeout(timeout)
        chunk = response.read1(
            min(config.read_chunk_bytes, config.max_response_bytes + 1)
        )
        read_any = True
        if time.monotonic() >= deadline:
            raise TimeoutError("превышен полный бюджет live probe")
        if not chunk:
            return
        yield chunk


def _response_lines(
    response: Any, config: GateConfig, deadline: float
) -> Iterable[bytes]:
    pending = b""
    size = 0
    for chunk in _response_chunks(response, config, deadline):
        size += len(chunk)
        if size > config.max_response_bytes:
            raise ValueError("превышен лимит SSE")
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if len(line) + 1 > config.max_sse_line_bytes:
                raise ValueError("превышен лимит SSE строки")
            yield line + b"\n"
        if len(pending) > config.max_sse_line_bytes:
            raise ValueError("превышен лимит SSE строки")
    if pending:
        yield pending


def run_live_hub_probe(base_url: str, config: GateConfig | None = None) -> Result:
    """G4: явный live opt-in, единый сетевой бюджет, обязательная дельта лога."""
    config = config or GateConfig.from_env()
    deadline = time.monotonic() + config.live_total_timeout_s
    before_id, before_size, before_tail = _log_snapshot(config)
    checks: dict[str, bool] = {}
    evidence: Result = {}
    token = ""
    try:
        url = urlsplit(base_url.rstrip("/"))
        if (
            url.scheme not in ("http", "https")
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("требуется http(s) URL без credentials/query/fragment")
        base = base_url.rstrip("/")
        origin = f"{url.scheme}://{url.netloc}"
        headers = {"X-Subagent-Id": "qa-product-gate-probe"}
        token = _api_key()
        if token:
            headers["Authorization"] = "Bearer " + token

        def get_json(endpoint: str, *, decode_json: bool = True) -> Any:
            with urlopen(
                Request(endpoint, headers=headers),
                timeout=_remaining_timeout(config, deadline),
            ) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                body = bytearray()
                for chunk in _response_chunks(response, config, deadline):
                    body.extend(chunk)
                    if len(body) > config.max_response_bytes:
                        raise ValueError("ответ превышает лимит")
                return json.loads(body) if decode_json else None

        get_json(origin + "/health", decode_json=False)
        checks["health_200"] = True
        models = get_json(base + "/models")
        entries = models.get("data") if isinstance(models, dict) else None
        if (
            not isinstance(entries, list)
            or not entries
            or any(
                not isinstance(m, dict)
                or not isinstance(m.get("id"), str)
                or not m["id"].strip()
                for m in entries
            )
        ):
            raise ValueError("пустой или невалидный список моделей")
        checks["models_nonempty"] = True
        model = config.model or entries[0]["id"]
        payload = {
            "model": model,
            "stream": True,
            "messages": [
                {
                    "role": "user",
                    "content": "Запомни код проверки: QA-47. В следующем ходе попрошу его повторить.",
                },
                {
                    "role": "assistant",
                    "content": "Код проверки QA-47 сохранён в контексте.",
                },
                {
                    "role": "user",
                    "content": "Повтори код проверки из предыдущих сообщений и кратко поясни цель проверки контекста.",
                },
            ],
        }
        request = Request(
            base + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                **headers,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        with urlopen(request, timeout=_remaining_timeout(config, deadline)) as response:
            checks["stream_http_200"] = response.status == 200
            if response.headers.get_content_type() != "text/event-stream":
                raise ValueError("ожидался Content-Type text/event-stream")
            frames = _parse_sse(
                _response_lines(response, config, deadline),
                config,
                stop_at_done=True,
                deadline=deadline,
            )
        checks["valid_sse_stop_done_content"] = True
        content = _channel(frames, "content")
        checks["multi_turn_context_retained"] = "QA-47" in content
        evidence.update(
            model=model, content_chars=len(content), frame_count=len(frames)
        )
    except (OSError, URLError, HTTPError, ValueError, TypeError) as exc:
        checks["probe_completed"] = False
        evidence["error"] = sanitize(f"{type(exc).__name__}: {exc}")
    try:
        with config.log_path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            after_id = (stat.st_dev, stat.st_ino)
            after_size = stat.st_size
            rotated = before_id != after_id or after_size < before_size
            if not rotated:
                stream.seek(before_size - len(before_tail))
                rotated = stream.read(len(before_tail)) != before_tail
            delta_size = after_size if rotated else after_size - before_size
            stream.seek(0 if rotated else before_size)
            delta = stream.read(min(delta_size, config.log_tail_bytes + 1))
    except OSError:
        checks["no_new_5xx_or_traceback"] = False
        evidence["log_inspection"] = {"status": "UNAVAILABLE", "complete": False}
    else:
        if before_id is None:
            checks["no_new_5xx_or_traceback"] = False
            evidence["log_inspection"] = {"status": "UNAVAILABLE", "complete": False}
        else:
            raw_text = delta.decode("utf-8", "replace")
            new_errors = [
                sanitize(line)
                for line in raw_text.splitlines()
                if re.search(config.log_error_pattern, line, re.I)
            ]
            complete = (
                not rotated
                and delta_size <= config.log_tail_bytes
                and len(delta) == delta_size
            )
            clean = not new_errors and complete
            checks["no_new_5xx_or_traceback"] = clean
            evidence["log_inspection"] = {
                "status": "PASS" if clean else "FAIL",
                "new_bytes": delta_size,
                "complete": complete,
                "rotated_or_truncated": rotated,
                "new_errors": new_errors,
            }
    result = _safe_tree(_result(checks, **evidence))
    # Включая секрет из dotenv, которого может не быть в окружении.
    if token:

        def redact(value: Any) -> Any:
            if isinstance(value, str):
                return value.replace(token, "[REDACTED]")
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        result = redact(result)
    return result


def _worktree_fingerprint(config: GateConfig | None = None) -> str:
    """HEAD + porcelain; не заменяет content-addressed snapshot оркестратора.

    Porcelain отражает набор изменённых путей, но не все изменения их содержимого.
    Для строгой привязки к байтам оркестратор передаёт fingerprint своего snapshot.
    Ошибка git не подменяется фиктивным fingerprint.
    """
    configured = os.environ.get("QA_GATE_WORKTREE_FINGERPRINT", "").strip()
    if configured:
        return configured
    try:
        parts = [
            subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                timeout=(
                    config.git_timeout_s
                    if config
                    else _positive_env("QA_GATE_GIT_TIMEOUT_S", 10.0)
                ),
            ).stdout
            for args in (
                ["rev-parse", "HEAD"],
                ["status", "--porcelain"],
            )
        ]
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return hashlib.sha256(parts[0] + b"\0" + parts[1]).hexdigest()


def _proof_checksum(proof: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        {key: value for key, value in proof.items() if key != "sha256"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def build_proof(
    gates: Mapping[str, Result], worktree_fingerprint: str | None = None
) -> Result:
    """Каноническая контрольная сумма результата, не криптографическая подпись."""
    fingerprint = (
        _worktree_fingerprint()
        if worktree_fingerprint is None
        else worktree_fingerprint
    )
    proof: Result = _safe_tree(
        {
            "schema_version": "1.0",
            "overall_status": "PASS"
            if fingerprint
            and gates
            and all(g.get("status") == "PASS" for g in gates.values())
            else "FAIL",
            "gates": dict(gates),
        }
    )
    # Fingerprint — непрозрачный идентификатор, его нельзя изменять sanitization.
    proof["worktree_fingerprint"] = fingerprint
    sensitivity = gates.get("G3")
    if sensitivity is not None:
        proof["canary_sensitivity"] = {
            key: sensitivity.get(key) for key in ("total", "killed", "kill_rate")
        }
    proof["sha256"] = _proof_checksum(proof)
    return proof


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("повторяющийся JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError(f"неконечное JSON число: {value}")


def verify_proof_contract(
    proof_path: Path,
    *,
    expected_fingerprint: str | None = None,
    allow_unbound: bool = False,
    require_provided_handoff: bool = True,
    required_gates: Iterable[str] = ("G1", "G2", "G3"),
    min_canary_total: int = 5,
) -> list[str]:
    """Fail-closed контракт перехода FSM: только пустой список разрешает переход.

    Вызывать без проверки exists() снаружи. Контрольная сумма не устанавливает
    автора proof; доверенный запуск и выбор required_gates — ответственность FSM.
    """
    try:
        proof = json.loads(
            proof_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, ValueError, UnicodeError, RecursionError):
        return ["proof отсутствует, не читается или содержит невалидный JSON"]
    if not isinstance(proof, dict):
        return ["proof должен быть JSON object"]
    errors: list[str] = []
    if proof.get("schema_version") != "1.0":
        errors.append("schema_version должен быть 1.0")
    if proof.get("overall_status") != "PASS":
        errors.append("overall_status должен быть PASS")
    try:
        if proof.get("sha256") != _proof_checksum(proof):
            errors.append("sha256: контрольная сумма не совпадает")
    except (ValueError, TypeError, OverflowError, RecursionError):
        errors.append("невозможно вычислить контрольную сумму")
    fingerprint = proof.get("worktree_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        errors.append("отсутствует непустой worktree_fingerprint")
    if not allow_unbound and (
        not isinstance(expected_fingerprint, str) or not expected_fingerprint.strip()
    ):
        errors.append("expected_fingerprint обязателен")
    if (
        isinstance(expected_fingerprint, str)
        and expected_fingerprint.strip()
        and fingerprint != expected_fingerprint
    ):
        errors.append("worktree_fingerprint не совпадает с ожидаемым")
    gates = proof.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates должен быть JSON object")
        gates = {}
    for name in required_gates:
        item = gates.get(name)
        if not isinstance(item, dict) or item.get("status") != "PASS":
            errors.append(f"{name}: обязательный gate отсутствует или не PASS")
    g2 = gates.get("G2")
    if require_provided_handoff and (
        not isinstance(g2, dict) or g2.get("scope") != "provided_handoff"
    ):
        errors.append("G2.scope должен быть provided_handoff")
    sensitivity = proof.get("canary_sensitivity")
    if not isinstance(sensitivity, dict):
        errors.append("отсутствует canary_sensitivity")
    else:
        rate = sensitivity.get("kill_rate")
        total = sensitivity.get("total")
        killed = sensitivity.get("killed")
        if type(rate) not in (int, float) or rate != 1.0:
            errors.append("canary_sensitivity.kill_rate должен быть 1.0")
        if type(total) is not int or total < min_canary_total:
            errors.append(
                f"canary_sensitivity.total должен быть целым >= {min_canary_total}"
            )
        if type(killed) is not int or killed != total:
            errors.append("canary_sensitivity.killed должен совпадать с total")
        g3 = gates.get("G3")
        if isinstance(g3, dict) and any(
            g3.get(key) != sensitivity.get(key)
            for key in ("total", "killed", "kill_rate")
        ):
            errors.append("canary_sensitivity не согласован с G3")
    return errors


def verify_fsm_transition(run_dir: Path, state: Mapping[str, Any]) -> list[str]:
    raw_ver = state.get("schema_version", 1)
    if type(raw_ver) is int:
        schema_ver = raw_ver
    elif isinstance(raw_ver, str) and re.fullmatch(r"\s*[+-]?\d+\s*", raw_ver):
        schema_ver = int(raw_ver.strip())
    else:
        return ["невалидный state.schema_version"]
    if schema_ver < 1:
        return ["невалидный state.schema_version"]
    qa_required = schema_ver >= 2 or bool(state.get("qa_gate_required", True))
    if not qa_required:
        return []
    try:
        cfg = GateConfig.from_env()
    except ValueError:
        return ["невалидная конфигурация окружения QA-гейта"]
    expected_fp = state.get("worktree_fingerprint")
    if not isinstance(expected_fp, str) or not expected_fp.strip():
        return ["отсутствует доверенный state.worktree_fingerprint"]
    required_gates = (
        ("G1", "G2", "G3", "G4")
        if state.get("live_gate_required")
        else ("G1", "G2", "G3")
    )
    return verify_proof_contract(
        run_dir / "qa-gate-proof.json",
        expected_fingerprint=expected_fp,
        require_provided_handoff=True,
        required_gates=required_gates,
        min_canary_total=cfg.min_canary_total,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI PASS не равен разрешению FSM: для него нужен verify_proof_contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--verify-sensitivity", action="store_true")
    parser.add_argument("--live-hub")
    parser.add_argument("--handoff", type=Path)
    parser.add_argument("--output-proof", type=Path)
    args = parser.parse_args(argv)
    gates: dict[str, Result] = {}
    fingerprint: str | None = None
    try:
        config = GateConfig.from_env()
        fingerprint = config.worktree_fingerprint or None
        default_all = not (args.verify_sensitivity or args.live_hub or args.handoff)
        if args.all or default_all:
            gates["G1"] = _checked(lambda: run_incident_replay_suite(config))
        if args.all or default_all or args.handoff:
            gates["G2"] = _checked(
                lambda: run_sdlc_integrity_check(
                    json.loads(args.handoff.read_text(encoding="utf-8"))
                    if args.handoff
                    else _MISSING
                )
            )
        if args.all or default_all or args.verify_sensitivity:
            gates["G3"] = _checked(lambda: run_canary_sensitivity_gate(config))
        if args.live_hub:
            gates["G4"] = _checked(lambda: run_live_hub_probe(args.live_hub, config))
    except (OSError, ValueError) as exc:
        gates["configuration"] = _result({"valid": False}, error=sanitize(str(exc)))
    proof = build_proof(gates, worktree_fingerprint=fingerprint)
    rendered = (
        json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )
    if args.output_proof:
        try:
            args.output_proof.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(sanitize(f"Не удалось записать proof: {exc}"), file=sys.stderr)
            return 1
    print(rendered, end="")
    return 0 if proof["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

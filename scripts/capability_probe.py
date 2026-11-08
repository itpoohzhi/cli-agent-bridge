#!/usr/bin/env python3
"""Capability Probe: проверки P1..P5 модели через мост и квитанция `probe-receipt/1`.

Спецификация: architecture-spec §4.3. Пробник ходит через мост (`/v1/chat/completions`),
чтобы проверить ровно тот путь, по которому модель будет работать: адаптер, эмуляцию
`tool_calls`, стриминг, изоляцию `<Think>`.

Проверки (все обязательны):
  P1 non-stream: ответ содержит nonce, finish_reason in {stop, length};
  P2 SSE: валидные `data:` чанки, `[DONE]`, nonce, нет склейки `[а-яёa-z]\\.[А-ЯЁA-Z]`;
  P3 round-trip `tool_calls` (`probe_echo`): ход 1 -> tool_calls, ход 2 -> `ECHO-<nonce>`;
  P4 лестница effort через `reasoning_effort` (2xx доказан, 400/422 не поддержан, иное -
     не доказан);
  P5 изоляция `<Think>`: до первого `delta.tool_calls` нет непустого `delta.content`.

Вердикт: `confirmed` <=> P1,P2,P3,P5 PASS и `efforts_proven` не пуст; `quarantine_failed` <=>
детерминированный FAIL (либо весь effort-лестница отвергнута 400/422); иначе `inconclusive`.
Коды выхода: 0 / 1 / 2 / 3 (ошибка использования).

Все эксплуатационные параметры - env (безопасные дефолты):
`BRIDGE_PROBE_REPEATS` (2), `BRIDGE_PROBE_TOOL_REPEATS` (2), `BRIDGE_PROBE_TIMEOUT_S` (120,
окно неактивности сокета), `BRIDGE_PROBE_SAFETY_CAP_S` (600, предохранитель одного запроса),
`BRIDGE_PROBE_MAX_TOKENS` (512), `BRIDGE_PROBE_EFFORT_MAX_TOKENS` (64),
`BRIDGE_PROBE_MAX_BYTES` (4 MiB), `BRIDGE_PROBE_LOCK_WAIT_S` (0, single-flight без ожидания),
`BRIDGE_PROBE_JOURNAL_PATH` (опциональный журнал ходов для поиска `LiveParserError` /
`RepetitionLoopDetected` по request_id), `BRIDGE_PROBE_EFFORT_LADDER` (CSV, если манифеста нет),
`BRIDGE_STATE_DIR`, `BRIDGE_GIT_SHA`, `BRIDGE_FLEET_PATH`, `DROID_DSH_BRIDGE_FLEET`.

Квитанция неизменяема и content-addressed (`state/probes/<sha256>.json`, `O_CREAT|O_EXCL`);
тексты промптов и ответов в неё не попадают - только оракулы, счётчики и request_id.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import discovery as _discovery  # noqa: E402
from core.backend_adapter import EFFORT_LEVELS  # noqa: E402
from core.param_adapter import resolve_state_dir  # noqa: E402
from core.probe_manifest_select import select_manifest as _select_core_manifest  # noqa: E402
from core.provider_manifest import ModelsDefaults, ProviderManifest  # noqa: E402

PROBE_VERSION = 1
RECEIPT_SCHEMA = "probe-receipt/1"
EXIT_CONFIRMED, EXIT_FAILED, EXIT_INCONCLUSIVE, EXIT_USAGE = 0, 1, 2, 3
VERDICT_CONFIRMED = "confirmed"
VERDICT_FAILED = "quarantine_failed"
VERDICT_INCONCLUSIVE = "inconclusive"
EXIT_CODES = {
    VERDICT_CONFIRMED: EXIT_CONFIRMED,
    VERDICT_FAILED: EXIT_FAILED,
    VERDICT_INCONCLUSIVE: EXIT_INCONCLUSIVE,
}
PASS, FAIL, INCONCLUSIVE, SKIPPED = "pass", "fail", "inconclusive", "skipped"
TOOL_NAME = "probe_echo"
GLUE_RE = re.compile(r"[а-яёa-z]\.[А-ЯЁA-Z]")
JOURNAL_MARKERS = ("LiveParserError", "RepetitionLoopDetected")
DEFAULT_HUB_URL = "http://127.0.0.1:9882/v1"
# Статусы: протокольная семантика, не эксплуатационные параметры.
_INCONCLUSIVE_STATUSES = frozenset({0, 401, 403, 408, 429, 500, 503, 504})
_LIMIT_MARKERS = (
    "rate_limit",
    "quota",
    "overloaded",
    "resource_exhausted",
    "insufficient_quota",
    "too many requests",
)
_SECRET_RE = re.compile(
    r"(Bearer\s+|api[_-]?key[:=]\s*)[a-zA-Z0-9_\-.]{8,}", re.IGNORECASE
)
_DEFAULT_LADDER = ModelsDefaults().probe_effort_ladder
_DEFAULT_EFFORT_CAP = ModelsDefaults().default_effort


# ---- env --------------------------------------------------------------------------------------


def _num(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


@dataclass(frozen=True)
class ProbeSettings:
    repeats: int = 2
    tool_repeats: int = 2
    timeout_s: float = 120.0
    safety_cap_s: float = 600.0
    max_tokens: int = 512
    effort_max_tokens: int = 64
    max_bytes: int = 4 << 20
    lock_wait_s: float = 0.0
    journal_path: Optional[str] = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ProbeSettings":
        base = cls()
        return cls(
            repeats=max(1, int(_num(env, "BRIDGE_PROBE_REPEATS", base.repeats))),
            tool_repeats=max(
                1, int(_num(env, "BRIDGE_PROBE_TOOL_REPEATS", base.tool_repeats))
            ),
            timeout_s=_num(env, "BRIDGE_PROBE_TIMEOUT_S", base.timeout_s)
            or base.timeout_s,
            safety_cap_s=_num(env, "BRIDGE_PROBE_SAFETY_CAP_S", base.safety_cap_s)
            or base.safety_cap_s,
            max_tokens=max(
                1, int(_num(env, "BRIDGE_PROBE_MAX_TOKENS", base.max_tokens))
            ),
            effort_max_tokens=max(
                1,
                int(
                    _num(env, "BRIDGE_PROBE_EFFORT_MAX_TOKENS", base.effort_max_tokens)
                ),
            ),
            max_bytes=max(
                1024, int(_num(env, "BRIDGE_PROBE_MAX_BYTES", base.max_bytes))
            ),
            lock_wait_s=_num(env, "BRIDGE_PROBE_LOCK_WAIT_S", base.lock_wait_s),
            journal_path=env.get("BRIDGE_PROBE_JOURNAL_PATH") or None,
        )


# ---- маскирование ---------------------------------------------------------------------------------


def mask_secret(text: str, api_key: Optional[str] = None) -> str:
    """Маскирует bearer-токены и (дословно) ключ моста в диагностическом тексте."""
    masked = _SECRET_RE.sub(r"\1[MASKED]", text)
    if api_key and len(api_key) >= 4:
        masked = masked.replace(api_key, "[MASKED]")
    return masked


# ---- транспорт ------------------------------------------------------------------------------------


@dataclass
class HttpResult:
    """Ответ транспорта; `status == 0` - сетевая ошибка/таймаут (`error` - slug)."""

    status: int = 0
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""
    lines: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def request_id(self) -> Optional[str]:
        for key, value in self.headers.items():
            if key.lower() == "x-request-id":
                return value
        return None


# (url, headers, payload, timeout_s, stream) -> HttpResult
Transport = Callable[[str, Mapping[str, str], Dict[str, Any], float, bool], HttpResult]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def urllib_transport(
    url: str,
    headers: Mapping[str, str],
    payload: Dict[str, Any],
    timeout_s: float,
    stream: bool,
    *,
    max_bytes: int,
    safety_cap_s: float,
) -> HttpResult:
    """POST JSON без прокси/редиректов; окно неактивности - таймаут сокета."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout_s) as response:
            hdrs = {k: v for k, v in response.headers.items()}
            if not stream:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    return HttpResult(response.status, hdrs, error="too_large")
                return HttpResult(response.status, hdrs, body)
            lines: List[str] = []
            total = 0
            for raw in response:
                total += len(raw)
                lines.append(raw.decode("utf-8", "replace").rstrip("\r\n"))
                if total > max_bytes:
                    return HttpResult(
                        response.status, hdrs, lines=lines, error="too_large"
                    )
                if time.monotonic() - started > safety_cap_s:
                    return HttpResult(
                        response.status, hdrs, lines=lines, error="safety_cap"
                    )
            return HttpResult(response.status, hdrs, lines=lines)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(max_bytes)
        except OSError:
            body = b""
        hdrs = {k: v for k, v in exc.headers.items()} if exc.headers else {}
        exc.close()
        return HttpResult(exc.code, hdrs, body)
    except (TimeoutError, urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        slug = (
            "timeout"
            if isinstance(reason, TimeoutError) or isinstance(exc, TimeoutError)
            else "network"
        )
        return HttpResult(0, error=slug)


# ---- результаты проверок ---------------------------------------------------------------------------


@dataclass
class CheckOutcome:
    result: str
    reason: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"result": self.result}
        if self.reason:
            out["reason"] = self.reason
        out.update(self.data)
        return out


def _status_class(status: int) -> str:
    """HTTP-статус -> `fail` (детерминированный) либо `inconclusive`."""
    if status in _INCONCLUSIVE_STATUSES:
        return INCONCLUSIVE
    if status >= 500 and status != 502:
        return INCONCLUSIVE
    return FAIL


def _is_limit_text(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _LIMIT_MARKERS)


def _json_body(result: HttpResult) -> Optional[Dict[str, Any]]:
    try:
        doc = json.loads(result.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _first_choice(doc: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    choices = doc.get("choices") if isinstance(doc, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return choices[0]
    return {}


@dataclass
class ProbeContext:
    model_id: str
    chat_url: str
    headers: Dict[str, str]
    http: Transport
    settings: ProbeSettings
    api_key: str = ""
    request_ids: List[str] = field(default_factory=list)
    journal_markers: bool = False

    def post(self, payload: Dict[str, Any], stream: bool) -> HttpResult:
        result = self.http(
            self.chat_url, self.headers, payload, self.settings.timeout_s, stream
        )
        rid = result.request_id
        if rid and rid not in self.request_ids:
            self.request_ids.append(rid)
        return result

    def base(self, messages: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"model": self.model_id, "messages": messages}
        payload.update(extra)
        return payload


def _transport_problem(res: HttpResult) -> Optional[CheckOutcome]:
    """Не-2xx, сетевая ошибка или обрыв транспорта -> итог проверки (иначе None)."""
    if res.status == 0 or res.error in ("timeout", "network"):
        return CheckOutcome(INCONCLUSIVE, res.error or "network")
    if not 200 <= res.status < 300:
        body_text = res.body.decode("utf-8", "replace") if res.body else ""
        if res.status in (400, 422) and _is_limit_text(body_text):
            return CheckOutcome(INCONCLUSIVE, "limit")
        return CheckOutcome(_status_class(res.status), "http_%d" % res.status)
    if res.error in ("too_large", "safety_cap"):
        return CheckOutcome(FAIL, res.error)
    return None


def _ids_have_journal_markers(
    ids: Sequence[str], body: str, settings: ProbeSettings
) -> bool:
    """`LiveParserError`/`RepetitionLoopDetected` в ответе или журнале хода (по request_id)."""
    if any(marker in body for marker in JOURNAL_MARKERS):
        return True
    if not settings.journal_path or not ids:
        return False
    try:
        size = os.path.getsize(settings.journal_path)
        with open(settings.journal_path, "rb") as handle:
            handle.seek(max(0, size - settings.max_bytes * 2))
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return False
    for line in text.splitlines():
        if any(rid in line for rid in ids) and any(m in line for m in JOURNAL_MARKERS):
            return True
    return False


def _new_nonce() -> str:
    return uuid.uuid4().hex[:12]


# ---- P1 / P2 ---------------------------------------------------------------------------------------


def _echo_prompt(nonce: str) -> str:
    return "Reply with exactly this token and nothing else: PROBE-" + nonce


def check_p1(ctx: ProbeContext) -> CheckOutcome:
    attempts = 0
    for _ in range(ctx.settings.repeats):
        attempts += 1
        nonce = _new_nonce()
        started = time.monotonic()
        res = ctx.post(
            ctx.base(
                [{"role": "user", "content": _echo_prompt(nonce)}],
                max_tokens=ctx.settings.max_tokens,
                stream=False,
            ),
            False,
        )
        problem = _transport_problem(res)
        if problem is not None:
            problem.data = {"attempts": attempts}
            return problem
        doc = _json_body(res)
        choice = _first_choice(doc)
        message = (
            choice.get("message") if isinstance(choice.get("message"), Mapping) else {}
        )
        content = message.get("content") if isinstance(message, Mapping) else None
        if (
            isinstance(content, str)
            and ("PROBE-" + nonce) in content
            and choice.get("finish_reason") in ("stop", "length")
        ):
            return CheckOutcome(
                PASS,
                data={
                    "attempts": attempts,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "request_ids": list(ctx.request_ids),
                },
            )
    return CheckOutcome(FAIL, "nonce_missing", {"attempts": attempts})


@dataclass
class SseParse:
    chunks: List[Mapping[str, Any]] = field(default_factory=list)
    done: bool = False
    error: Optional[str] = None  # slug: frame_invalid | stream_error | stream_limit


def parse_sse(lines: Sequence[str]) -> SseParse:
    """Разбор `data:`-строк SSE: валидный JSON-объект на каждый кадр, `[DONE]`, in-stream error."""
    out = SseParse()
    for line in lines:
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            out.done = True
            break
        try:
            chunk = json.loads(payload)
        except ValueError:
            out.error = "frame_invalid"
            return out
        if not isinstance(chunk, dict):
            out.error = "frame_invalid"
            return out
        if chunk.get("error"):
            text = json.dumps(chunk["error"], ensure_ascii=False)
            out.error = "stream_limit" if _is_limit_text(text) else "stream_error"
            return out
        out.chunks.append(chunk)
    return out


def _delta(chunk: Mapping[str, Any]) -> Mapping[str, Any]:
    delta = _first_choice(chunk).get("delta")
    return delta if isinstance(delta, Mapping) else {}


def _stream_problem(res: HttpResult, parsed: SseParse) -> Optional[CheckOutcome]:
    if parsed.error == "stream_limit":
        return CheckOutcome(INCONCLUSIVE, "stream_limit")
    if parsed.error:
        return CheckOutcome(FAIL, parsed.error)
    return None


def check_p2(ctx: ProbeContext) -> CheckOutcome:
    attempts = 0
    last_chunks = 0
    for _ in range(ctx.settings.repeats):
        attempts += 1
        nonce = _new_nonce()
        res = ctx.post(
            ctx.base(
                [{"role": "user", "content": _echo_prompt(nonce)}],
                max_tokens=ctx.settings.max_tokens,
                stream=True,
            ),
            True,
        )
        problem = _transport_problem(res)
        if problem is not None:
            problem.data = {"attempts": attempts}
            return problem
        parsed = parse_sse(res.lines)
        problem = _stream_problem(res, parsed)
        if problem is not None:
            problem.data = {"attempts": attempts}
            return problem
        last_chunks = len(parsed.chunks)
        if not parsed.done:
            return CheckOutcome(
                FAIL, "no_done", {"attempts": attempts, "chunks": last_chunks}
            )
        pieces = [
            d["content"]
            for d in (_delta(c) for c in parsed.chunks)
            if isinstance(d.get("content"), str) and d["content"]
        ]
        text = "".join(pieces)
        if not pieces:
            continue
        if GLUE_RE.search(text):
            return CheckOutcome(
                FAIL, "glued_steps", {"attempts": attempts, "chunks": last_chunks}
            )
        if ("PROBE-" + nonce) in text:
            return CheckOutcome(
                PASS, data={"attempts": attempts, "chunks": last_chunks}
            )
    return CheckOutcome(
        FAIL, "nonce_missing", {"attempts": attempts, "chunks": last_chunks}
    )


# ---- P3 / P5 ---------------------------------------------------------------------------------------


def _tools_spec() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": "Echo the nonce back to the caller.",
                "parameters": {
                    "type": "object",
                    "properties": {"nonce": {"type": "string"}},
                    "required": ["nonce"],
                },
            },
        }
    ]


def _tool_prompt(nonce: str) -> str:
    return (
        'Call the function %s exactly once with the argument nonce="%s". '
        "Do not answer in text before calling it." % (TOOL_NAME, nonce)
    )


def _tool_payload(
    ctx: ProbeContext, messages: List[Dict[str, Any]], stream: bool
) -> Dict[str, Any]:
    return ctx.base(
        messages,
        tools=_tools_spec(),
        tool_choice="auto",
        max_tokens=ctx.settings.max_tokens,
        stream=stream,
    )


def _p3_round_trip(ctx: ProbeContext, nonce: str) -> CheckOutcome:
    user = {"role": "user", "content": _tool_prompt(nonce)}
    first = ctx.post(_tool_payload(ctx, [user], False), False)
    problem = _transport_problem(first)
    if problem is not None:
        return problem
    doc = _json_body(first)
    choice = _first_choice(doc)
    message = (
        choice.get("message") if isinstance(choice.get("message"), Mapping) else {}
    )
    calls = message.get("tool_calls") if isinstance(message, Mapping) else None
    if not isinstance(calls, list) or not calls or not isinstance(calls[0], Mapping):
        return CheckOutcome(FAIL, "no_tool_calls")
    function = calls[0].get("function")
    function = function if isinstance(function, Mapping) else {}
    if function.get("name") != TOOL_NAME:
        return CheckOutcome(FAIL, "wrong_tool_name")
    arguments = function.get("arguments")
    try:
        parsed_args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except ValueError:
        return CheckOutcome(FAIL, "arguments_not_json")
    if not isinstance(parsed_args, Mapping) or parsed_args.get("nonce") != nonce:
        return CheckOutcome(FAIL, "nonce_mismatch")
    if choice.get("finish_reason") != "tool_calls":
        return CheckOutcome(FAIL, "finish_reason")
    call_id = str(calls[0].get("id") or "call_probe")
    assistant = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": TOOL_NAME,
                    "arguments": json.dumps({"nonce": nonce}),
                },
            }
        ],
    }
    tool = {"role": "tool", "tool_call_id": call_id, "content": "ECHO-" + nonce}
    second = ctx.post(_tool_payload(ctx, [user, assistant, tool], False), False)
    problem = _transport_problem(second)
    if problem is not None:
        return problem
    final = _first_choice(_json_body(second)).get("message")
    content = final.get("content") if isinstance(final, Mapping) else None
    if not isinstance(content, str) or ("ECHO-" + nonce) not in content:
        return CheckOutcome(FAIL, "echo_missing")
    body_text = first.body.decode("utf-8", "replace") + second.body.decode(
        "utf-8", "replace"
    )
    if _ids_have_journal_markers(ctx.request_ids, body_text, ctx.settings):
        return CheckOutcome(FAIL, "journal_marker")
    return CheckOutcome(PASS)


def check_p3(ctx: ProbeContext) -> CheckOutcome:
    """Требуются **все** `BRIDGE_PROBE_TOOL_REPEATS` попыток."""
    attempts = 0
    for _ in range(ctx.settings.tool_repeats):
        attempts += 1
        outcome = _p3_round_trip(ctx, _new_nonce())
        if outcome.result != PASS:
            outcome.data = {"attempts": attempts}
            return outcome
    return CheckOutcome(PASS, data={"attempts": attempts})


def check_p5(ctx: ProbeContext) -> CheckOutcome:
    """До первого `delta.tool_calls` нет непустого `delta.content` (преамбулы - в reasoning)."""
    for _ in range(ctx.settings.tool_repeats):
        nonce = _new_nonce()
        res = ctx.post(
            _tool_payload(
                ctx, [{"role": "user", "content": _tool_prompt(nonce)}], True
            ),
            True,
        )
        problem = _transport_problem(res)
        if problem is not None:
            return problem
        parsed = parse_sse(res.lines)
        problem = _stream_problem(res, parsed)
        if problem is not None:
            return problem
        saw_tool_call = False
        for chunk in parsed.chunks:
            delta = _delta(chunk)
            content = delta.get("content")
            has_content = isinstance(content, str) and content.strip() != ""
            if delta.get("tool_calls"):
                saw_tool_call = True
                if has_content:
                    return CheckOutcome(FAIL, "content_with_tool_calls")
                break
            if has_content:
                return CheckOutcome(FAIL, "content_before_tool_calls")
        if saw_tool_call:
            return CheckOutcome(PASS)
    return CheckOutcome(FAIL, "no_tool_call")


# ---- P4 ----------------------------------------------------------------------------------------------


def effort_ladder(
    manifest: Optional[ProviderManifest], model_id: str, env: Mapping[str, str]
) -> Tuple[str, ...]:
    """`efforts_pin` модели, иначе `probe_effort_ladder` манифеста, иначе env/дефолт."""
    if manifest is not None:
        rule = manifest.rule_for(model_id)
        if rule is not None and rule.efforts_pin:
            return tuple(rule.efforts_pin)
        return tuple(manifest.models_defaults.probe_effort_ladder)
    raw = env.get("BRIDGE_PROBE_EFFORT_LADDER")
    if raw:
        parsed = tuple(p.strip() for p in raw.split(",") if p.strip() in EFFORT_LEVELS)
        if parsed:
            return parsed
    return tuple(_DEFAULT_LADDER)


def check_p4(ctx: ProbeContext, ladder: Sequence[str]) -> Dict[str, List[str]]:
    proven: List[str] = []
    unsupported: List[str] = []
    inconclusive: List[str] = []
    for effort in ladder:
        res = ctx.post(
            ctx.base(
                [{"role": "user", "content": "Reply with: ok"}],
                max_tokens=ctx.settings.effort_max_tokens,
                stream=False,
                reasoning_effort=effort,
            ),
            False,
        )
        if 200 <= res.status < 300 and res.error is None:
            proven.append(effort)
        elif res.status in (400, 422):
            unsupported.append(effort)
        else:
            inconclusive.append(effort)
    order = {name: idx for idx, name in enumerate(EFFORT_LEVELS)}

    def key(name: str) -> int:
        return order.get(name, len(order))

    return {
        "proven": sorted(proven, key=key),
        "unsupported": sorted(unsupported, key=key),
        "inconclusive": sorted(inconclusive, key=key),
    }


def pick_default_effort(
    proven: Sequence[str], cap: Optional[str] = None
) -> Optional[str]:
    """Максимум доказанного по `EFFORT_LEVELS`, не выше `cap`; иначе минимальный доказанный."""
    if not proven:
        return None
    order = {name: idx for idx, name in enumerate(EFFORT_LEVELS)}
    ranked = sorted(proven, key=lambda e: order.get(e, len(order)))
    limit = order.get(cap or _DEFAULT_EFFORT_CAP, len(order))
    allowed = [e for e in ranked if order.get(e, len(order)) <= limit]
    return allowed[-1] if allowed else ranked[0]


# ---- квитанция ---------------------------------------------------------------------------------------


def canonical_bytes(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def write_receipt(receipt: Mapping[str, Any], state_dir: Path) -> Tuple[str, Path]:
    """Content-addressed запись `state/probes/<sha256>.json` через `O_CREAT|O_EXCL`."""
    data = canonical_bytes(receipt)
    sha = hashlib.sha256(data).hexdigest()
    directory = Path(state_dir) / "probes"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (sha + ".json")
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        if (
            path.read_bytes() != data
        ):  # sha256 коллизия/порча: молча перезаписывать нельзя
            raise
        return sha, path
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return sha, path


def _git_sha(env: Mapping[str, str]) -> str:
    forced = env.get("BRIDGE_GIT_SHA")
    if forced and re.fullmatch(r"[0-9a-f]{40}", forced):
        return forced
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "0" * 40
    return out if re.fullmatch(r"[0-9a-f]{40}", out) else "0" * 40


def fleet_path(env: Mapping[str, str]) -> Path:
    raw = env.get("BRIDGE_FLEET_PATH") or env.get("DROID_DSH_BRIDGE_FLEET")
    return Path(os.path.expanduser(raw)) if raw else REPO_ROOT / "fleet.json"


def _fleet_sha(env: Mapping[str, str]) -> str:
    try:
        return hashlib.sha256(fleet_path(env).read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


def _fingerprint(
    manifest: Optional[ProviderManifest], env: Mapping[str, str]
) -> Tuple[Dict[str, Optional[str]], str]:
    if manifest is None:
        parts: Dict[str, Optional[str]] = {
            "binary_path": None,
            "binary_sha256": None,
            "version": None,
        }
        return parts, hashlib.sha256(
            _discovery.NO_FINGERPRINT_SEED.encode("utf-8")
        ).hexdigest()
    parts = _discovery.fingerprint_parts(manifest, env)
    return parts, _discovery.compute_fingerprint(manifest, env)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---- single-flight ---------------------------------------------------------------------------------------


class ProbeBusy(Exception):
    """Проба этой модели (или квота группы) уже занята другим процессом."""


@contextlib.contextmanager
def _flock(path: Path, wait_s: float) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+")
    deadline = time.monotonic() + wait_s
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ProbeBusy(path.name)
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


@contextlib.contextmanager
def _quota_slot(
    state_dir: Path, group: str, capacity: int, wait_s: float
) -> Iterator[None]:
    """Семафор квоты группы: `capacity` lock-файлов, занимается любой свободный."""
    deadline = time.monotonic() + wait_s
    with contextlib.ExitStack() as stack:
        while True:
            acquired = False
            for index in range(max(1, capacity)):
                try:
                    stack.enter_context(
                        _flock(
                            state_dir
                            / "locks"
                            / ("probe-quota-%s-%d.lock" % (group, index)),
                            0,
                        )
                    )
                except ProbeBusy:
                    continue
                acquired = True
                break
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise ProbeBusy("quota-" + group)
            time.sleep(0.05)
        yield


def lock_path(state_dir: Path, provider_id: str, model_id: str) -> Path:
    digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:16]
    return Path(state_dir) / "locks" / ("probe-%s-%s.lock" % (provider_id, digest))


# ---- основной сценарий ---------------------------------------------------------------------------------------


@dataclass
class ProbeResult:
    verdict: str
    receipt: Dict[str, Any]
    receipt_sha256: str = ""
    receipt_path: Optional[Path] = None
    fingerprint_sha256: str = ""
    efforts_proven: Tuple[str, ...] = ()
    default_effort: Optional[str] = None
    reused: bool = False
    reason: Optional[str] = None

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.verdict]


def _subagent_id(provider_id: str, model_id: str) -> str:
    return (
        "probe-"
        + hashlib.sha256((provider_id + "|" + model_id).encode("utf-8")).hexdigest()[:8]
    )


def _find_confirmed_receipt(
    state_dir: Path,
    provider_id: str,
    model_id: str,
    binary_sha: Optional[str],
    version: Optional[str],
) -> Optional[Tuple[str, Path, Dict[str, Any]]]:
    directory = Path(state_dir) / "probes"
    if not directory.is_dir():
        return None
    best: Optional[Tuple[str, Path, Dict[str, Any]]] = None
    for path in sorted(directory.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        fp = doc.get("fingerprint") if isinstance(doc, dict) else None
        if (
            isinstance(doc, dict)
            and doc.get("schema") == RECEIPT_SCHEMA
            and doc.get("probe_version") == PROBE_VERSION
            and doc.get("verdict") == VERDICT_CONFIRMED
            and doc.get("provider_id") == provider_id
            and doc.get("model_id") == model_id
            and isinstance(fp, dict)
            and fp.get("sha256") == binary_sha
            and fp.get("version") == version
        ):
            if best is None or str(doc.get("finished_at")) > str(
                best[2].get("finished_at")
            ):
                best = (path.stem, path, doc)
    return best


def run_probe(
    model_id: str,
    provider_id: str,
    hub_url: str,
    api_key: str,
    manifest: Optional[ProviderManifest] = None,
    http: Optional[Transport] = None,
    env: Optional[Mapping[str, str]] = None,
    *,
    state_dir: Optional[Path] = None,
    force: bool = True,
    now_fn: Callable[[], str] = _now_iso,
) -> ProbeResult:
    """P1..P5 -> вердикт -> квитанция. HTTP идёт только через `http` (инъекция в тестах).

    `force=False` переиспользует уже подтверждённую квитанцию с тем же отпечатком.
    Бросает `ProbeBusy`, если проба модели/квоты занята и `BRIDGE_PROBE_LOCK_WAIT_S` истёк.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    settings = ProbeSettings.from_env(source)
    state = Path(state_dir) if state_dir else resolve_state_dir(source)
    fp_parts, fp_sha = _fingerprint(manifest, source)
    if not force:
        found = _find_confirmed_receipt(
            state,
            provider_id,
            model_id,
            fp_parts.get("binary_sha256"),
            fp_parts.get("version"),
        )
        if found is not None:
            sha, path, doc = found
            proven = tuple(doc.get("efforts_proven") or ())
            return ProbeResult(
                VERDICT_CONFIRMED,
                doc,
                sha,
                path,
                fp_sha,
                proven,
                doc.get("default_effort"),
                True,
            )
    transport = http or functools.partial(
        urllib_transport,
        max_bytes=settings.max_bytes,
        safety_cap_s=settings.safety_cap_s,
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
        "X-Subagent-Id": _subagent_id(provider_id, model_id),
        "X-Review-Profile": "Zero-Canon",
    }
    ctx = ProbeContext(
        model_id=model_id,
        chat_url=hub_url.rstrip("/") + "/chat/completions",
        headers=headers,
        http=transport,
        settings=settings,
        api_key=api_key,
    )
    started_at = now_fn()
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            _flock(lock_path(state, provider_id, model_id), settings.lock_wait_s)
        )
        if manifest is not None and manifest.quota_group:
            stack.enter_context(
                _quota_slot(
                    state,
                    manifest.quota_group,
                    manifest.probe.max_parallel,
                    settings.lock_wait_s,
                )
            )
        checks, p4 = _run_checks(ctx, effort_ladder(manifest, model_id, source))
    finished_at = now_fn()
    proven = tuple(p4["proven"])
    verdict = _verdict(checks, p4)
    cap = manifest.models_defaults.default_effort if manifest is not None else None
    default_effort = pick_default_effort(proven, cap)
    receipt: Dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "probe_version": PROBE_VERSION,
        "provider_id": provider_id,
        "model_id": model_id,
        "fingerprint": {
            "binary_path": fp_parts.get("binary_path"),
            "sha256": fp_parts.get("binary_sha256"),
            "version": fp_parts.get("version"),
        },
        "bridge": {"git_sha": _git_sha(source), "fleet_sha256": _fleet_sha(source)},
        "started_at": started_at,
        "finished_at": finished_at,
        "checks": {name: out.as_dict() for name, out in checks.items()},
        "verdict": verdict,
        "efforts_proven": list(proven),
        "default_effort": default_effort,
    }
    receipt["checks"]["P4"] = p4
    sha, path = write_receipt(receipt, state)
    return ProbeResult(verdict, receipt, sha, path, fp_sha, proven, default_effort)


def _run_checks(
    ctx: ProbeContext, ladder: Sequence[str]
) -> Tuple[Dict[str, CheckOutcome], Dict[str, List[str]]]:
    """P1 -> P2 -> P3 -> P4 -> P5; остановка на inconclusive и на FAIL P1."""
    checks: Dict[str, CheckOutcome] = {}
    p4: Dict[str, List[str]] = {"proven": [], "unsupported": [], "inconclusive": []}
    stop = False
    for name, func in (("P1", check_p1), ("P2", check_p2), ("P3", check_p3)):
        if stop:
            checks[name] = CheckOutcome(SKIPPED)
            continue
        checks[name] = func(ctx)
        if checks[name].result == INCONCLUSIVE or (
            name == "P1" and checks[name].result == FAIL
        ):
            stop = True
    if not stop:
        p4 = check_p4(ctx, ladder)
        checks["P5"] = check_p5(ctx)
    else:
        checks["P5"] = CheckOutcome(SKIPPED)
        p4 = {"proven": [], "unsupported": [], "inconclusive": list(ladder)}
    return checks, p4


def _verdict(
    checks: Mapping[str, CheckOutcome], p4: Mapping[str, Sequence[str]]
) -> str:
    required = [checks[name].result for name in ("P1", "P2", "P3", "P5")]
    if FAIL in required:
        return VERDICT_FAILED
    if INCONCLUSIVE in required or SKIPPED in required:
        return VERDICT_INCONCLUSIVE
    if p4["proven"]:
        return VERDICT_CONFIRMED
    if p4["unsupported"] and not p4["inconclusive"]:
        return VERDICT_FAILED  # вся лестница отвергнута 400/422
    return VERDICT_INCONCLUSIVE


# ---- CLI ----------------------------------------------------------------------------------------------------


def resolve_api_key(env: Mapping[str, str]) -> str:
    key = env.get("BRIDGE_KEY") or env.get("HUB_API_KEY")
    if not key:
        dsh_env = Path.home() / ".dsh" / ".env"
        try:
            for line in dsh_env.read_text(encoding="utf-8").splitlines():
                if line.startswith("BRIDGE_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    return key or env.get("OPENAI_API_KEY") or ""


def select_manifest(
    manifests: Sequence[ProviderManifest], model_id: str, provider_id: Optional[str]
) -> Tuple[Optional[ProviderManifest], Optional[str]]:
    """Манифест провайдера: по `--provider` либо единственный, чей include/static матчит модель."""
    cand = _select_core_manifest(manifests, model_id, provider_id, strict_ambiguous=True)
    return cand.manifest, cand.problem


def probe_cli(
    model_id: str,
    *,
    provider_id: Optional[str] = None,
    hub_url: str = DEFAULT_HUB_URL,
    force: bool = False,
    as_json: bool = False,
    providers_dir: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    http: Optional[Transport] = None,
    out: Any = None,
) -> int:
    """Общая точка входа для `capability_probe.py` и `smoke_models.py --probe-model`."""
    source: Mapping[str, str] = os.environ if env is None else env
    stream = out or sys.stdout
    from adapters import ADAPTER_KINDS
    from core.provider_manifest import load_manifests

    loaded = load_manifests(providers_dir, ADAPTER_KINDS, env=source)
    manifest, problem = select_manifest(loaded.manifests, model_id, provider_id)
    if manifest is None:
        print("USAGE: %s (model=%s)" % (problem, model_id), file=sys.stderr)
        return EXIT_USAGE
    if not manifest.probe.enabled:
        print(
            "USAGE: probe_disabled (provider=%s)" % manifest.provider_id,
            file=sys.stderr,
        )
        return EXIT_USAGE
    api_key = resolve_api_key(source)
    if not api_key:
        print("USAGE: bridge key not found (BRIDGE_KEY/HUB_API_KEY)", file=sys.stderr)
        return EXIT_USAGE
    try:
        result = run_probe(
            model_id,
            manifest.provider_id,
            hub_url,
            api_key,
            manifest,
            http=http,
            env=source,
            force=force,
        )
    except ProbeBusy as exc:
        print(mask_secret("INCONCLUSIVE: probe busy (%s)" % exc, api_key), file=stream)
        return EXIT_INCONCLUSIVE
    summary = {
        "verdict": result.verdict,
        "provider_id": manifest.provider_id,
        "model_id": model_id,
        "receipt": str(result.receipt_path) if result.receipt_path else None,
        "receipt_sha256": result.receipt_sha256,
        "efforts_proven": list(result.efforts_proven),
        "default_effort": result.default_effort,
        "reused": result.reused,
        "checks": {
            name: check.get("result", "proven" if check.get("proven") else "-")
            for name, check in result.receipt["checks"].items()
        },
    }
    if as_json:
        print(
            mask_secret(
                json.dumps(summary, ensure_ascii=False, sort_keys=True), api_key
            ),
            file=stream,
        )
    else:
        print(
            mask_secret(
                "%s model=%s provider=%s efforts=%s receipt=%s"
                % (
                    result.verdict.upper(),
                    model_id,
                    manifest.provider_id,
                    ",".join(result.efforts_proven) or "-",
                    result.receipt_path,
                ),
                api_key,
            ),
            file=stream,
        )
    return result.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capability probe P1..P5 for one model"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", default=None)
    parser.add_argument(
        "--hub-url", default=os.environ.get("HUB_BRIDGE_URL", DEFAULT_HUB_URL)
    )
    parser.add_argument("--providers-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", dest="as_json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code not in (0, None) else 0
    return probe_cli(
        args.model,
        provider_id=args.provider,
        hub_url=args.hub_url,
        force=args.force,
        as_json=args.as_json,
        providers_dir=args.providers_dir,
    )


if __name__ == "__main__":
    sys.exit(main())

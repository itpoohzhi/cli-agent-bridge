#!/usr/bin/env python3
"""Parallel smoke runner for models defined in the canonical models.md file."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, NamedTuple


DEFAULT_MODELS_MD = Path(
    os.environ.get("MODELS_MD_PATH") or "~/Мой диск/Context/models.md"
).expanduser()
DEFAULT_MODEL_NOTES_MD = Path(
    os.environ.get("MODEL_NOTES_MD_PATH") or "~/Мой диск/Context/model-notes.md"
).expanduser()
DEFAULT_HUB_URL = os.environ.get("HUB_BRIDGE_URL", "http://127.0.0.1:9882/v1")

_LAST_WORKER_PGID: int | None = None
_WORKER_PGIDS: dict[int, int] = {}


class ModelEntry(NamedTuple):
    role: str
    model_id: str
    effort: str
    family: str


class ModelLimitException(Exception):
    """Raised when a model cannot run because of a temporary usage limit."""

    def __init__(
        self,
        detail: str,
        model_id: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.model_id = model_id
        self.status_code = status_code


def _clean_markdown_cell(value: str) -> str:
    return value.strip().strip("` ")


def _family_for_model(model_id: str, fallback: str = "") -> str:
    lowered = model_id.lower()
    if lowered.startswith("claude-"):
        return "Anthropic"
    if lowered.startswith("gpt-"):
        return "OpenAI"
    if lowered.startswith("gemini-"):
        return "Google"
    if lowered.startswith("muse-"):
        return "Meta"
    if "deepseek" in lowered:
        return "DeepSeek"
    return fallback.strip()


def parse_models_md(path: Path) -> list[ModelEntry]:
    """Extract model, effort, family, and role entries from models.md tables."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Канонический файл models.md не найден: {path}")

    content = path.read_text(encoding="utf-8")
    entries: list[ModelEntry] = []
    current_role = "General"
    current_table_role = ""
    table_schema: dict[str, int] | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            header = line[4:].strip()
            current_role = header.split("—", 1)[0].strip()
            current_table_role = ""
            table_schema = None
            continue
        if line.startswith("## "):
            table_schema = None
            current_table_role = ""

        if not (line.startswith("|") and line.endswith("|")):
            continue

        cells = [cell.strip() for cell in line.strip("|").split("|")]
        normalized = [_clean_markdown_cell(cell).lower() for cell in cells]
        if all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells):
            continue

        effort_index = next(
            (idx for idx, value in enumerate(normalized) if value == "effort"),
            None,
        )
        model_index = next(
            (
                idx
                for idx, value in enumerate(normalized)
                if value.startswith("модель") or value.startswith("слот")
            ),
            None,
        )
        if effort_index is not None and model_index is not None:
            family_index = next(
                (idx for idx, value in enumerate(normalized) if value.startswith("family")),
                -1,
            )
            role_index = next(
                (idx for idx, value in enumerate(normalized) if value.startswith("роль")),
                -1,
            )
            table_schema = {
                "model": model_index,
                "effort": effort_index,
                "family": family_index,
                "role": role_index,
            }
            current_table_role = ""
            continue

        if table_schema is None:
            continue

        model_index = table_schema["model"]
        effort_index = table_schema["effort"]
        family_index = table_schema["family"]
        role_index = table_schema["role"]
        if model_index >= len(cells) or effort_index >= len(cells):
            continue

        if role_index >= 0 and role_index < len(cells):
            role_cell = cells[role_index].strip()
            if role_cell:
                cleaned_role = re.sub(r"[`*_]", "", role_cell).strip()
                cleaned_role = cleaned_role.split("(", 1)[0].strip()
                if cleaned_role:
                    current_table_role = cleaned_role
        role = current_table_role or current_role

        model_cell = cells[model_index]
        model_ids = re.findall(r"`([a-zA-Z0-9][a-zA-Z0-9._/-]*)`", model_cell)
        if not model_ids:
            plain_model = _clean_markdown_cell(model_cell)
            match = re.search(r"[a-zA-Z0-9][a-zA-Z0-9._/-]*", plain_model)
            model_ids = [match.group(0)] if match else []
        if not model_ids:
            continue
        if "+" not in model_cell and len(model_ids) > 1:
            model_ids = model_ids[:1]

        effort_cell = cells[effort_index]
        efforts = re.findall(
            r"`(xhigh|high|medium|low|max|off)`", effort_cell, flags=re.IGNORECASE
        )
        if not efforts:
            match = re.search(
                r"\b(xhigh|high|medium|low|max|off)\b",
                effort_cell,
                flags=re.IGNORECASE,
            )
            efforts = [match.group(1)] if match else [""]
        efforts = [effort.lower() for effort in efforts]

        annotated_efforts: list[tuple[str, set[str]]] = []
        for annotation in re.finditer(
            r"`?(xhigh|high|medium|low|max|off)`?\s*\(([^)]*)\)",
            effort_cell,
            flags=re.IGNORECASE,
        ):
            providers = {
                provider.strip().lower()
                for provider in re.split(r"\s*,\s*|\s*;\s*", annotation.group(2))
                if provider.strip()
            }
            annotated_efforts.append((annotation.group(1).lower(), providers))

        family_cell = cells[family_index] if 0 <= family_index < len(cells) else ""
        family_parts = [
            re.sub(r"[`*]", "", part).strip()
            for part in re.split(r"\s*\+\s*|\s*;\s*", family_cell)
            if re.sub(r"[`*]", "", part).strip()
        ]
        fallback_family = family_parts[0] if family_parts else family_cell.strip()
        effort_values = {effort.lower() for effort in efforts}

        for idx, model_id in enumerate(model_ids):
            if model_id.lower() in {
                "модель",
                "слот",
                "пакет",
                "роль",
                "local",
                "none",
                "—",
                "-",
            }:
                continue
            effort = efforts[idx] if idx < len(efforts) else efforts[0]
            family_hint = family_parts[idx] if idx < len(family_parts) else fallback_family
            family = _family_for_model(model_id, family_hint)

            family_lower = family.lower()
            for annotated_effort, providers in annotated_efforts:
                if family_lower in providers:
                    effort = annotated_effort
                    break

            model_lower = model_id.lower()
            if model_lower.startswith("deepseek-v4.1-flash") and "off" in effort_values:
                effort = "off"
            if model_lower == "gemini-3.8-flash" and (
                effort in {"", "off"} or "medium" in effort_values
            ):
                effort = "medium"

            entries.append(ModelEntry(role, model_id, effort, family))

    seen: set[tuple[str, str]] = set()
    unique_entries: list[ModelEntry] = []
    for entry in entries:
        key = (entry.role, entry.model_id)
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)
    return unique_entries


def parse_temp_off_models(notes_path: Path = DEFAULT_MODEL_NOTES_MD) -> set[str]:
    """Return model IDs explicitly marked TEMP OFF in bullet or table rows."""
    notes_path = Path(notes_path).expanduser()
    if not notes_path.is_file():
        return set()

    content = notes_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    section_lines: list[str] = []
    section_level: int | None = None

    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if section_level is None:
            if heading and "temp off" in heading.group(2).lower():
                section_level = len(heading.group(1))
            continue
        if heading and len(heading.group(1)) <= section_level:
            break
        section_lines.append(line)

    if section_level is None:
        return set()

    section = "\n".join(section_lines)
    section_clean = section.replace("`", "")
    if re.search(
        r"список\s+temp\s+off\s+пуст",
        section_clean,
        flags=re.IGNORECASE,
    ):
        return set()

    excluded = {
        "temp-off",
        "temp_off",
        "limit-blocked",
        "quota_window",
        "transport_failures",
        "run-id",
    }
    models: set[str] = set()
    for line in section_lines:
        line_clean = line.replace("`", "")
        stripped = line.lstrip()
        if not (stripped.startswith(("-", "*", "+")) or stripped.startswith("|")):
            continue
        if not re.search(r"\btemp\s+off\b", line_clean, flags=re.IGNORECASE):
            continue
        for candidate in re.findall(r"`([^`]+)`", line):
            candidate = candidate.strip()
            lowered = candidate.lower()
            if re.fullmatch(r"temp\s+off", lowered, flags=re.IGNORECASE):
                continue
            if lowered in excluded:
                continue
            if lowered.endswith((".md", ".json", ".tsv", ".py")):
                continue
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/-]*", candidate):
                continue
            if "-" not in candidate and "/" not in candidate:
                continue
            models.add(candidate)
    return models


def mask_secret(text: str) -> str:
    """Mask bearer tokens and API keys in diagnostic text."""
    return re.sub(
        r"(Bearer\s+|api[_-]?key[:=]\s*)[a-zA-Z0-9_\-.]{8,}",
        r"\1[MASKED]",
        text,
        flags=re.IGNORECASE,
    )


def is_model_limit_error(status_code: int | None, text: str) -> bool:
    """Return whether an HTTP or streamed error represents a model usage limit."""
    if status_code == 429:
        return True
    lowered = (text or "").lower()
    markers = (
        "rate_limit",
        "rate limit",
        "quota",
        "exhausted",
        "resource_exhausted",
        "model_cooldown",
        "penalized_until",
        "limit_exceeded",
        "temp off",
        "temp_off",
        "blocked_by_limit",
    )
    return any(marker in lowered for marker in markers)


def build_bridge_payload(
    model_id: str,
    effort: str = "",
    prompt: str = "ping",
    max_tokens: int = 16,
    stream: bool = True,
) -> dict[str, Any]:
    """Build the OpenAI-compatible bridge request for a canonical model ID."""
    normalized_effort = effort.lower().strip()
    if model_id == "gemini-3.8-flash" and normalized_effort == "off":
        normalized_effort = "medium"

    target_model = model_id
    target_effort = normalized_effort
    thinking_disabled = False

    if model_id in ("deepseek-v4.1-flash", "deepseek-v4.1-flash-free"):
        target_model = "deepseek-v4.1-flash-free"
        target_effort = "off"
        thinking_disabled = True
    elif model_id in ("gemini-4-argon-high", "gemini-4-argon-medium"):
        target_model = "gemini-4-argon"
        target_effort = normalized_effort or (
            "high" if model_id.endswith("-high") else "medium"
        )
    elif model_id in (
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-low",
    ):
        target_model = "gemini-3.8-flash"
        target_effort = normalized_effort or model_id.rsplit("-", 1)[-1]
    else:
        claude_match = re.match(
            r"^(claude-(?:sonnet|opus|haiku)-5-5)-(xhigh|high|medium|low|max)$",
            model_id,
        )
        if claude_match:
            target_model = claude_match.group(1)
            target_effort = normalized_effort or claude_match.group(2)

    payload: dict[str, Any] = {
        "model": target_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if target_effort in {"high", "xhigh", "medium", "low", "max", "off"}:
        payload["reasoning_effort"] = target_effort
    if thinking_disabled:
        payload["thinking"] = {"type": "disabled"}
    return payload


def _resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("BRIDGE_KEY") or os.environ.get("HUB_API_KEY")
    if not key:
        dsh_env = Path.home() / ".dsh" / ".env"
        if dsh_env.is_file():
            try:
                for line in dsh_env.read_text(encoding="utf-8").splitlines():
                    if line.startswith("BRIDGE_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
            except OSError:
                pass
    return key or os.environ.get("OPENAI_API_KEY") or "test-smoke-key"


def _read_error_body(response: Any) -> str:
    try:
        body = response.read()
    except Exception:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", "replace")
    return str(body)


def smoke_test_model(
    hub_url: str,
    model_id: str,
    timeout_s: float = 20.0,
    api_key: str | None = None,
    effort: str = "",
    subagent_id: str = "",
    use_subprocess: bool = False,
    strict_limits: bool = False,
    raise_on_limit: bool = False,
) -> tuple[bool, str, float]:
    """Send one isolated OpenAI-compatible streaming smoke request."""
    if use_subprocess:
        ok, status, latency, _pid = smoke_test_model_subprocess(
            hub_url,
            model_id,
            timeout_s=timeout_s,
            api_key=api_key,
            effort=effort,
            subagent_id=subagent_id,
        )
        return ok, status, latency

    key = _resolve_api_key(api_key)
    endpoint = hub_url.rstrip("/") + "/chat/completions"
    payload = build_bridge_payload(model_id, effort=effort, stream=True)
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("X-Subagent-Id", subagent_id or f"smoke-{model_id}")

    started = time.monotonic()
    ttft: float | None = None
    got_done = False
    try:
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                status_code = response.getcode()
                if status_code != 200:
                    error_body = _read_error_body(response)
                    elapsed = time.monotonic() - started
                    if is_model_limit_error(status_code, error_body):
                        detail = mask_secret(error_body.strip()) or f"HTTP {status_code}"
                        raise ModelLimitException(
                            detail,
                            model_id=model_id,
                            status_code=status_code,
                        )
                    detail = mask_secret(error_body.strip())
                    status = f"HTTP {status_code}"
                    if detail:
                        status += f": {detail}"
                    return False, status, elapsed

                for raw_line in response:
                    line = raw_line.decode("utf-8", "replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        got_done = True
                        break
                    try:
                        chunk = json.loads(data_text)
                    except ValueError:
                        continue

                    if isinstance(chunk, dict) and (
                        "error" in chunk or str(chunk.get("type", "")).lower() == "error"
                    ):
                        elapsed = time.monotonic() - started
                        error_text = json.dumps(chunk, ensure_ascii=False)
                        if is_model_limit_error(status_code, error_text):
                            raise ModelLimitException(
                                mask_secret(error_text),
                                model_id=model_id,
                                status_code=status_code,
                            )
                        return False, mask_secret(f"STREAM_ERROR: {error_text}"), elapsed

                    choices = chunk.get("choices") or [] if isinstance(chunk, dict) else []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        if (
                            delta.get("content")
                            or delta.get("reasoning_content")
                            or delta.get("thinking")
                        ) and ttft is None:
                            ttft = time.monotonic() - started

                elapsed = time.monotonic() - started
                if ttft is not None:
                    return True, "STREAM_OK", ttft
                if got_done:
                    return True, "DONE_OK", elapsed
                return False, "No stream chunks", elapsed
        except ModelLimitException:
            raise
        except urllib.error.HTTPError as exc:
            elapsed = time.monotonic() - started
            error_body = _read_error_body(exc)
            error_text = error_body or str(exc.reason)
            if is_model_limit_error(exc.code, error_text):
                raise ModelLimitException(
                    mask_secret(error_text.strip()) or f"HTTP {exc.code}",
                    model_id=model_id,
                    status_code=exc.code,
                )
            status = f"HTTP {exc.code}"
            if error_text:
                status += f": {mask_secret(error_text.strip())}"
            return False, status, elapsed
        except Exception as exc:
            detail = mask_secret(str(exc))
            return False, "ERROR", detail  # type: ignore[return-value]
    except ModelLimitException as exc:
        if raise_on_limit:
            raise
        return (
            not strict_limits,
            "SKIPPED_LIMIT",
            f"ModelLimitException: {exc}",
        )  # type: ignore[return-value]


def smoke_test_model_subprocess(
    hub_url: str,
    model_id: str,
    timeout_s: float = 30.0,
    api_key: str | None = None,
    effort: str = "",
    subagent_id: str = "",
) -> tuple[bool, str, float, int]:
    """Run one smoke check in a child process with its own process group."""
    global _LAST_WORKER_PGID

    command = [
        sys.executable,
        __file__,
        "--worker-single",
        "--hub-url",
        hub_url,
        "--model",
        model_id,
        "--effort",
        effort,
        "--subagent-id",
        subagent_id,
        "--timeout",
        str(timeout_s),
    ]
    environment = os.environ.copy()
    if api_key:
        environment["BRIDGE_KEY"] = api_key

    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s + 10.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                proc.kill()
            stdout, stderr = proc.communicate()
        _LAST_WORKER_PGID = proc.pid
        _WORKER_PGIDS[proc.pid] = proc.pid
        return False, "Timeout", time.monotonic() - started, proc.pid

    payload: dict[str, Any] | None = None
    for line in reversed(stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except ValueError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break

    if payload is None:
        diagnostic = stderr.strip() or stdout.strip() or f"worker exited {proc.returncode}"
        _LAST_WORKER_PGID = proc.pid
        _WORKER_PGIDS[proc.pid] = proc.pid
        return (
            False,
            mask_secret(f"Worker error: {diagnostic}"),
            time.monotonic() - started,
            proc.pid,
        )

    worker_pgid = payload.get("pgid")
    if not isinstance(worker_pgid, int):
        worker_pgid = proc.pid
    _LAST_WORKER_PGID = worker_pgid
    _WORKER_PGIDS[proc.pid] = worker_pgid

    latency_value = payload.get("latency", time.monotonic() - started)
    try:
        latency = float(latency_value)
    except (TypeError, ValueError):
        latency = 0.0

    return (
        bool(payload.get("ok")),
        str(payload.get("status", "Worker returned no status")),
        latency,
        proc.pid,
    )


def deduplicate_models_for_parallel(
    entries: list[ModelEntry], all_roles: bool = False
) -> list[ModelEntry]:
    """Remove duplicate parallel checks while preserving the first role seen."""
    seen: set[tuple[str, ...]] = set()
    result: list[ModelEntry] = []
    for entry in entries:
        if all_roles:
            key = (entry.role, entry.model_id, entry.effort.lower())
        else:
            key = (entry.model_id, entry.effort.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def run_parallel_smoke(
    entries: list[ModelEntry],
    hub_url: str,
    timeout_s: float = 45.0,
    max_workers: int | None = None,
    use_subprocesses: bool = False,
    temp_off_models: set[str] | None = None,
    api_key: str | None = None,
    strict_limits: bool = False,
) -> list[dict[str, Any]]:
    """Run all supplied model checks concurrently and preserve input ordering."""
    blocked_models = temp_off_models or set()
    worker_count = max_workers or min(128, max(16, len(entries) or 1))
    results: list[dict[str, Any] | None] = [None] * len(entries)

    def base_result(index: int, entry: ModelEntry) -> dict[str, Any]:
        safe_role = re.sub(r"[^a-zA-Z0-9_-]", "-", entry.role.lower())
        return {
            "index": index,
            "role": entry.role,
            "model_id": entry.model_id,
            "effort": entry.effort,
            "family": entry.family,
            "subagent_id": f"smoke-{index}-{safe_role}-{entry.model_id}",
        }

    def execute(index: int, entry: ModelEntry) -> dict[str, Any]:
        result = base_result(index, entry)
        try:
            if entry.model_id in blocked_models:
                raise ModelLimitException(
                    "model is declared TEMP OFF",
                    model_id=entry.model_id,
                    status_code=None,
                )

            if use_subprocesses:
                ok, status, latency, worker_pid = smoke_test_model_subprocess(
                    hub_url,
                    entry.model_id,
                    timeout_s=timeout_s,
                    api_key=api_key,
                    effort=entry.effort,
                    subagent_id=result["subagent_id"],
                )
                result["worker_pid"] = worker_pid
                result["worker_pgid"] = _WORKER_PGIDS.get(worker_pid, worker_pid)
            else:
                ok, status, latency_value = smoke_test_model(
                    hub_url,
                    entry.model_id,
                    timeout_s=timeout_s,
                    api_key=api_key,
                    effort=entry.effort,
                    subagent_id=result["subagent_id"],
                    strict_limits=strict_limits,
                )
                if isinstance(latency_value, (int, float)):
                    latency = float(latency_value)
                else:
                    latency = 0.0
                    result["detail"] = str(latency_value)
            if status == "SKIPPED_LIMIT" and strict_limits:
                ok = False
            result.update(ok=ok, status=status, latency=latency)
        except ModelLimitException as exc:
            result.update(
                ok=not strict_limits,
                status="SKIPPED_LIMIT",
                detail=f"ModelLimitException: {exc}",
                latency=0.0,
            )
        except Exception as exc:
            result.update(
                ok=False,
                status=mask_secret(f"Error: {exc}"),
                latency=0.0,
            )
        return result

    futures: dict[concurrent.futures.Future[dict[str, Any]], int] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        for index, entry in enumerate(entries):
            future = executor.submit(execute, index, entry)
            futures[future] = index

        for future in concurrent.futures.as_completed(futures):
            index = futures[future]
            results[index] = future.result()

    return [result for result in results if result is not None]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test runner for models defined in models.md"
    )
    parser.add_argument("--models-md", type=Path, default=DEFAULT_MODELS_MD)
    parser.add_argument("--model-notes-md", type=Path, default=DEFAULT_MODEL_NOTES_MD)
    parser.add_argument("--hub-url", type=str, default=DEFAULT_HUB_URL)
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--effort", type=str, default="")
    parser.add_argument("--subagent-id", type=str, default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--all-roles", action="store_true")
    parser.add_argument("--subprocesses", action="store_true")
    parser.add_argument("--strict-limits", action="store_true")
    parser.add_argument("--worker-single", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_single:
        ok, status, latency = smoke_test_model(
            args.hub_url,
            args.model,
            timeout_s=args.timeout,
            effort=args.effort,
            subagent_id=args.subagent_id,
        )
        print(
            json.dumps(
                {
                    "ok": ok,
                    "status": status,
                    "latency": latency,
                    "pgid": os.getpgrp(),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0 if ok else 1

    models = parse_models_md(args.models_md)
    if args.model:
        models = [entry for entry in models if entry.model_id == args.model]
    models = deduplicate_models_for_parallel(models, all_roles=args.all_roles)

    if not models:
        print("FAIL: No models found matching criteria.")
        return 1

    print(f"=== Smoke Models Matrix (Found {len(models)} model entries) ===")
    print(
        f"{'Role':<24} | {'Model ID':<32} | {'Family':<12} | "
        f"{'Status':<20} | {'Latency':<10}"
    )
    print("-" * 112)

    if args.live and not args.dry_run:
        temp_off_models = parse_temp_off_models(args.model_notes_md)
        results = run_parallel_smoke(
            models,
            args.hub_url,
            timeout_s=args.timeout,
            max_workers=args.max_workers,
            use_subprocesses=args.subprocesses,
            temp_off_models=temp_off_models,
            strict_limits=args.strict_limits,
        )
    else:
        results = [
            {
                "role": entry.role,
                "model_id": entry.model_id,
                "family": entry.family,
                "ok": True,
                "status": "CONFIGURED",
                "latency": 0.0,
            }
            for entry in models
        ]

    for result in results:
        latency = (
            f"{result['latency']:.2f}s"
            if args.live and not args.dry_run
            else "-"
        )
        print(
            f"{result['role']:<24} | {result['model_id']:<32} | "
            f"{result['family']:<12} | {result['status']:<20} | {latency:<10}"
        )

    if args.dry_run:
        print("\nPASS: Configuration is valid (dry-run mode).")
        return 0
    if not args.live:
        print("\nNOTE: Run with --live to perform actual network requests.")
        return 0

    stream_ok_count = sum(
        1 for result in results if result.get("status") in ("STREAM_OK", "DONE_OK")
    )
    skipped_limit_count = sum(
        1 for result in results if result.get("status") == "SKIPPED_LIMIT"
    )
    print(
        f"\nSUMMARY: total={len(results)} stream_ok={stream_ok_count} "
        f"skipped_limit={skipped_limit_count}"
    )
    if len(results) > 0 and stream_ok_count == 0:
        return 1
    return 0 if all(bool(result["ok"]) for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())


#!/usr/bin/env python3
"""Parallel smoke runner for models defined in the canonical models.md file."""

from __future__ import annotations

import argparse
import concurrent.futures
from functools import lru_cache
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
from typing import Any, Literal, NamedTuple, overload


DEFAULT_MODELS_MD = Path(
    os.environ.get("MODELS_MD_PATH") or "~/Мой диск/Context/models.md"
).expanduser()
DEFAULT_MODEL_NOTES_MD = Path(
    os.environ.get("MODEL_NOTES_MD_PATH") or "~/Мой диск/Context/model-notes.md"
).expanduser()
DEFAULT_HUB_URL = os.environ.get("HUB_BRIDGE_URL", "http://127.0.0.1:9882/v1")


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


def _catalog_lock_path() -> Path:
    """Сайдкар каталога: `BRIDGE_CATALOG_LOCK` либо `<BRIDGE_STATE_DIR>/catalog.lock.json`."""
    explicit = os.environ.get("BRIDGE_CATALOG_LOCK")
    if explicit:
        return Path(explicit).expanduser()
    state = os.environ.get("BRIDGE_STATE_DIR") or "~/work/cli-agent-bridge/state"
    return Path(state).expanduser() / "catalog.lock.json"


def _catalog_families() -> dict[str, str]:
    """`models[mid].family` из сайдкара каталога; нет файла/поля - пустая карта."""
    try:
        data = json.loads(_catalog_lock_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, dict):
        return {}
    families: dict[str, str] = {}
    for model_id, record in models.items():
        family = record.get("family") if isinstance(record, dict) else None
        if isinstance(family, str) and family.strip():
            families[str(model_id)] = family.strip()
    return families


def _effort_overrides() -> dict[str, str]:
    """Data-driven override эффорта: env `BRIDGE_SMOKE_EFFORT_OVERRIDES` = JSON {"model": "effort"}."""
    raw = os.environ.get("BRIDGE_SMOKE_EFFORT_OVERRIDES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(model): str(effort).lower()
        for model, effort in data.items()
        if isinstance(effort, str) and effort.strip()
    }


def parse_models_md(path: Path) -> list[ModelEntry]:
    """Extract model, effort, family, and role entries from models.md tables."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Канонический файл models.md не найден: {path}")

    content = path.read_text(encoding="utf-8")
    catalog_families = _catalog_families()
    effort_overrides = _effort_overrides()
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
            (idx for idx, value in enumerate(normalized) if value == "effort"), None
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
            family = catalog_families.get(model_id) or family_hint.strip()

            family_lower = family.lower()
            explicit_annotation_matched = False
            for annotated_effort, providers in annotated_efforts:
                if family_lower in providers:
                    effort = annotated_effort
                    explicit_annotation_matched = True
                    break

            if not explicit_annotation_matched and model_id in effort_overrides:
                effort = effort_overrides[model_id]

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
    section_lines: list[str] = []
    section_level: int | None = None

    for line in content.splitlines():
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

    section_clean = "\n".join(section_lines).replace("`", "")
    if re.search(r"список\s+temp\s+off\s+пуст", section_clean, flags=re.IGNORECASE):
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
            if lowered in excluded or lowered.endswith((".md", ".json", ".tsv", ".py")):
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


def is_model_limit_error(status_code: int, body: str) -> bool:
    """Return whether an HTTP or streamed error is an explicit model limit."""
    if status_code <= 0 or not body:
        return False
    if status_code == 429:
        return True

    structured_markers = {
        "rate_limit_error",
        "rate_limit_exceeded",
        "quota_exceeded",
        "resource_exhausted",
        "insufficient_quota",
        "model_cooldown",
        "temp_off",
        "blocked_by_limit",
    }
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict):
            error_type = str(error.get("type") or "").lower()
            error_code = str(error.get("code") or "").lower()
            if error_type in structured_markers or error_code in structured_markers:
                return True

    if status_code >= 500:
        return False
    if status_code not in (200, 400, 403, 409, 413, 422):
        return False

    lowered = body.lower()
    explicit_phrases = (
        "rate limit",
        "rate_limit",
        "quota exceeded",
        "quota_exceeded",
        "resource_exhausted",
        "resource exhausted",
        "insufficient_quota",
        "model_cooldown",
        "penalized_until",
        "temp_off",
        "temp off",
        "blocked_by_limit",
        "too many requests",
    )
    return any(phrase in lowered for phrase in explicit_phrases)


def _fleet_path() -> Path:
    """`BRIDGE_FLEET_PATH`, затем `DROID_DSH_BRIDGE_FLEET`, иначе `<repo>/fleet.json`."""
    raw = os.environ.get("BRIDGE_FLEET_PATH") or os.environ.get("DROID_DSH_BRIDGE_FLEET")
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[1] / "fleet.json"


@lru_cache(maxsize=1)
def _load_fleet_config() -> tuple[frozenset[str], dict[str, str]]:
    fleet_path = _fleet_path()
    try:
        data = json.loads(fleet_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset(), {}

    raw_models = data.get("models", {}) if isinstance(data, dict) else {}
    if isinstance(raw_models, dict):
        models = {str(model_id) for model_id in raw_models}
    elif isinstance(raw_models, list):
        models = set()
        for item in raw_models:
            if isinstance(item, str):
                models.add(item)
            elif isinstance(item, dict):
                model_id = item.get("id") or item.get("model") or item.get("name")
                if model_id:
                    models.add(str(model_id))
    else:
        models = set()

    raw_aliases = data.get("aliases", {}) if isinstance(data, dict) else {}
    aliases: dict[str, str] = {}
    if isinstance(raw_aliases, dict):
        for alias, target in raw_aliases.items():
            if isinstance(target, str):
                aliases[str(alias)] = target
            elif isinstance(target, dict):
                target_id = next(filter(None, map(target.get, ("model", "target", "id", "backend_id"))), None)
                if target_id:
                    aliases[str(alias)] = str(target_id)
    return frozenset(models), aliases


def build_bridge_payload(
    model_id: str,
    effort: str = "",
    prompt: str = "ping",
    max_tokens: int = 16,
    stream: bool = True,
) -> dict[str, Any]:
    """Build a bridge request using fleet.json as the wire-model authority."""
    models, aliases = _load_fleet_config()
    wire_model = model_id
    target_effort = effort.lower().strip()

    if model_id in aliases:
        wire_model = aliases[model_id]
        target_effort = target_effort or next((e for e in ("minimal", "low", "medium", "high", "xhigh", "max") if model_id.lower().endswith("-" + e)), "")
    elif model_id not in models and f"{model_id}-free" in models:
        wire_model = f"{model_id}-free"
    elif model_id not in models:
        suffix_match = re.match(
            r"^(.*)-(minimal|low|medium|high|xhigh|max)$", model_id, re.IGNORECASE
        )
        if suffix_match and suffix_match.group(1) in models:
            wire_model = suffix_match.group(1)
            if not target_effort:
                target_effort = suffix_match.group(2).lower()

    payload: dict[str, Any] = {
        "model": wire_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if target_effort in {"minimal", "low", "medium", "high", "xhigh", "max", "off"}:
        payload["reasoning_effort"] = target_effort
    if target_effort == "off":
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
        return ok, status, float(latency)

    key = _resolve_api_key(api_key)
    endpoint = hub_url.rstrip("/") + "/chat/completions"
    payload = build_bridge_payload(model_id, effort=effort, stream=True)
    request = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"), method="POST"
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
                    elapsed = float(time.monotonic() - started)
                    if is_model_limit_error(status_code, error_body):
                        detail = mask_secret(error_body.strip()) or f"HTTP {status_code}"
                        raise ModelLimitException(detail, model_id, status_code)
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

                    if isinstance(chunk, dict) and chunk.get("error"):
                        elapsed = float(time.monotonic() - started)
                        error_text = json.dumps(chunk, ensure_ascii=False)
                        if is_model_limit_error(status_code, error_text):
                            raise ModelLimitException(
                                mask_secret(error_text), model_id, status_code
                            )
                        return False, mask_secret(f"ERROR: {error_text}"), elapsed

                    choices = chunk.get("choices") or [] if isinstance(chunk, dict) else []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        if (
                            delta.get("content")
                            or delta.get("reasoning_content")
                            or delta.get("thinking")
                        ) and ttft is None:
                            ttft = time.monotonic() - started

                elapsed = float(time.monotonic() - started)
                if ttft is not None:
                    return True, "STREAM_OK", float(ttft)
                if got_done:
                    return True, "DONE_OK", elapsed
                return False, "ERROR: No stream chunks", elapsed
        except ModelLimitException:
            raise
        except urllib.error.HTTPError as exc:
            elapsed = float(time.monotonic() - started)
            error_body = _read_error_body(exc)
            error_text = error_body or str(exc.reason)
            if is_model_limit_error(exc.code, error_text):
                raise ModelLimitException(
                    mask_secret(error_text.strip()) or f"HTTP {exc.code}",
                    model_id,
                    exc.code,
                )
            status = f"HTTP {exc.code}"
            if error_text:
                status += f": {mask_secret(error_text.strip())}"
            return False, status, elapsed
        except Exception as exc:
            elapsed = float(time.monotonic() - started)
            return False, mask_secret(f"ERROR: {exc}"), elapsed
    except ModelLimitException:
        if raise_on_limit:
            raise
        return not strict_limits, "SKIPPED_LIMIT", float(time.monotonic() - started)


@overload
def smoke_test_model_subprocess(
    hub_url: str,
    model_id: str,
    timeout_s: float = 30.0,
    api_key: str | None = None,
    effort: str = "",
    subagent_id: str = "",
    return_pgid: Literal[False] = ...,
) -> tuple[bool, str, float, int]: ...


@overload
def smoke_test_model_subprocess(
    hub_url: str,
    model_id: str,
    timeout_s: float = 30.0,
    api_key: str | None = None,
    effort: str = "",
    subagent_id: str = "",
    *,
    return_pgid: Literal[True],
) -> tuple[bool, str, float, int, int]: ...


def smoke_test_model_subprocess(
    hub_url: str,
    model_id: str,
    timeout_s: float = 30.0,
    api_key: str | None = None,
    effort: str = "",
    subagent_id: str = "",
    return_pgid: bool = False,
) -> tuple[bool, str, float, int] | tuple[bool, str, float, int, int]:
    """Run one smoke check in a child process with its own process group."""
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
    observed_pgid: int | None = None
    try:
        observed_pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pass

    def result_tuple(
        ok: bool, status: str, latency: float, worker_pgid: int
    ) -> tuple[bool, str, float, int] | tuple[bool, str, float, int, int]:
        base = (ok, status, float(latency), proc.pid)
        if return_pgid:
            return base + (worker_pgid,)
        return base

    try:
        stdout, stderr = proc.communicate(timeout=timeout_s + 10.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(observed_pgid or proc.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(observed_pgid or proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                proc.kill()
            stdout, stderr = proc.communicate()
        return result_tuple(
            False, "ERROR: Timeout", time.monotonic() - started, observed_pgid or proc.pid
        )

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
        return result_tuple(
            False,
            mask_secret(f"ERROR: Worker error: {diagnostic}"),
            time.monotonic() - started,
            observed_pgid or proc.pid,
        )

    json_pgid = payload.get("pgid")
    worker_pgid = observed_pgid
    if worker_pgid is None and isinstance(json_pgid, int) and json_pgid > 0:
        worker_pgid = json_pgid
    if worker_pgid is None:
        worker_pgid = proc.pid

    latency_value = payload.get("latency", time.monotonic() - started)
    try:
        latency = float(latency_value)
    except (TypeError, ValueError):
        latency = 0.0
    return result_tuple(
        bool(payload.get("ok")),
        str(payload.get("status", "ERROR: Worker returned no status")),
        latency,
        worker_pgid,
    )


def deduplicate_models_for_parallel(
    entries: list[ModelEntry], all_roles: bool = False
) -> list[ModelEntry]:
    """Remove duplicate parallel checks while preserving the first role seen."""
    seen: set[tuple[str, ...]] = set()
    result: list[ModelEntry] = []
    for entry in entries:
        key = (
            (entry.role, entry.model_id, entry.effort.lower())
            if all_roles
            else (entry.model_id, entry.effort.lower())
        )
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
                    "model is declared TEMP OFF", entry.model_id, None
                )

            if use_subprocesses:
                ok, status, latency, worker_pid, worker_pgid = smoke_test_model_subprocess(
                    hub_url,
                    entry.model_id,
                    timeout_s=timeout_s,
                    api_key=api_key,
                    effort=entry.effort,
                    subagent_id=result["subagent_id"],
                    return_pgid=True,
                )
                result["worker_pid"] = worker_pid
                result["worker_pgid"] = worker_pgid
            else:
                ok, status, latency = smoke_test_model(
                    hub_url,
                    entry.model_id,
                    timeout_s=timeout_s,
                    api_key=api_key,
                    effort=entry.effort,
                    subagent_id=result["subagent_id"],
                    strict_limits=strict_limits,
                    raise_on_limit=True,
                )

            normalized_status = status
            if status.startswith("ERROR:"):
                normalized_status = status
                result["detail"] = status.split(":", 1)[1].strip()
            elif status.startswith("HTTP "):
                normalized_status = status
                if ":" in status:
                    result["detail"] = status.split(":", 1)[1].strip()
            elif status == "SKIPPED_LIMIT":
                result["detail"] = "model usage limit"
                if strict_limits:
                    ok = False
            result.update(ok=ok, status=normalized_status, latency=float(latency))
        except ModelLimitException as exc:
            result.update(
                ok=not strict_limits,
                status="SKIPPED_LIMIT",
                detail=f"ModelLimitException: {exc}",
                latency=0.0,
            )
        except Exception as exc:
            detail = mask_secret(str(exc))
            result.update(
                ok=False,
                status=f"ERROR: {detail}",
                detail=detail,
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


def _load_capability_probe() -> Any:
    """Подгружает `capability_probe.py` рядом со скриптом (каталог scripts не пакет)."""
    cached = sys.modules.get("capability_probe")
    if cached is not None:
        return cached
    import importlib.util

    path = Path(__file__).resolve().with_name("capability_probe.py")
    spec = importlib.util.spec_from_file_location("capability_probe", path)
    if spec is None or spec.loader is None:
        raise ImportError("capability_probe.py not found")
    module = importlib.util.module_from_spec(spec)
    sys.modules["capability_probe"] = module
    spec.loader.exec_module(module)
    return module


def _run_probe_model(args: argparse.Namespace) -> int:
    """`--probe-model`: коды выхода 0 confirmed / 1 quarantine_failed / 2 inconclusive / 3 usage."""
    try:
        probe = _load_capability_probe()
    except (ImportError, OSError) as exc:
        print(f"USAGE: capability probe unavailable: {exc}", file=sys.stderr)
        return 3
    return int(
        probe.probe_cli(
            args.probe_model,
            provider_id=args.provider or None,
            hub_url=args.hub_url,
            force=args.force,
            as_json=args.as_json,
            providers_dir=args.providers_dir,
        )
    )


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument(
        "--probe-model",
        type=str,
        default="",
        help="run the capability probe (P1..P5) for one canonical model id",
    )
    parser.add_argument("--provider", type=str, default="", help="provider id for --probe-model")
    parser.add_argument("--force", action="store_true", help="re-probe even if confirmed")
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--providers-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.probe_model:
        return _run_probe_model(args)

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
        results = run_parallel_smoke(
            models,
            args.hub_url,
            timeout_s=args.timeout,
            max_workers=args.max_workers,
            use_subprocesses=args.subprocesses,
            temp_off_models=parse_temp_off_models(args.model_notes_md),
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
        latency = f"{result['latency']:.2f}s" if args.live and not args.dry_run else "-"
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
    if results and stream_ok_count == 0:
        return 1
    return 0 if all(bool(result["ok"]) for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())


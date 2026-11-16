#!/usr/bin/env python3
"""Parallel smoke runner for models defined in the canonical models.md file."""

from __future__ import annotations

import argparse
import concurrent.futures
from collections.abc import Iterator
import hashlib
import importlib
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Literal, NamedTuple, overload
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.stream_outcome import OutcomeKind, StreamOutcomeClassifier

DEFAULT_MODELS_MD = Path(os.environ.get("MODELS_MD_PATH") or "~/Мой диск/Context/models.md").expanduser()
DEFAULT_MODEL_NOTES_MD = Path(os.environ.get("MODEL_NOTES_MD_PATH") or "~/Мой диск/Context/model-notes.md").expanduser()
DEFAULT_HUB_URL = os.environ.get("HUB_BRIDGE_URL", "http://127.0.0.1:9882/v1")

class ModelEntry(NamedTuple):
    role: str
    model_id: str
    effort: str
    family: str

class ModelLimitException(Exception):
    """Raised when a model cannot run because of a temporary usage limit."""

    def __init__(self, detail: str, model_id: str='', status_code: int | None=None) -> None:
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
    raw = os.environ.get('BRIDGE_SMOKE_EFFORT_OVERRIDES', '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(model): str(effort).lower() for model, effort in data.items() if isinstance(effort, str) and effort.strip()}

def parse_models_md(path: Path) -> list[ModelEntry]:
    """Извлекает уникальные пары роль/модель из канонических таблиц."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f'Канонический файл models.md не найден: {path}')
    families, overrides = (_catalog_families(), _effort_overrides())
    entries: dict[tuple[str, str], ModelEntry] = {}
    for role, cells, schema in _model_rows(path.read_text(encoding='utf-8')):
        for entry in _model_entries(role, cells, schema, families, overrides):
            entries.setdefault((entry.role, entry.model_id), entry)
    return list(entries.values())

def _column_index(values: list[str], prefixes: tuple[str, ...]) -> int:
    return next((i for i, value in enumerate(values) if value.startswith(prefixes)), -1)

def _model_schema(cells: list[str]) -> dict[str, int] | None:
    values = [_clean_markdown_cell(cell).lower() for cell in cells]
    model = _column_index(values, ('модель', 'слот'))
    effort = next((i for i, value in enumerate(values) if value == 'effort'), -1)
    if min(model, effort) < 0:
        return None
    return dict(model=model, effort=effort, family=_column_index(values, ('family',)), role=_column_index(values, ('роль',)))

def _indexed_cell(cells: list[str], index: int) -> str:
    return cells[index] if 0 <= index < len(cells) else ''

def _model_cells(line: str) -> list[str]:
    if not (line.startswith("|") and line.endswith("|")):
        return []
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    return [] if all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells) else cells

def _model_rows(content: str) -> Iterator[tuple[str, list[str], dict[str, int]]]:
    """Хранит только состояние заголовка и наследуемой роли таблицы."""
    role, table_role, schema = ('General', '', None)
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith('### '):
            role = line[4:].strip().split('—', 1)[0].strip()
        if line.startswith(('## ', '### ')):
            table_role, schema = ('', None)
        cells = _model_cells(line)
        if not cells:
            continue
        header = _model_schema(cells)
        if header is not None:
            schema, table_role = (header, '')
            continue
        if not _model_row_fits(cells, schema):
            continue
        assert schema is not None
        cleaned_role = re.sub('[`*_]', '', _indexed_cell(cells, schema['role'])).strip().split('(', 1)[0].strip()
        table_role = cleaned_role or table_role
        yield (table_role or role, cells, schema)

def _model_row_fits(cells: list[str], schema: dict[str, int] | None) -> bool:
    return schema is not None and max(schema['model'], schema['effort']) < len(cells)

def _cell_models(cell: str) -> list[str]:
    models = re.findall('`([a-zA-Z0-9][a-zA-Z0-9._/-]*)`', cell)
    if not models:
        match = re.search('[a-zA-Z0-9][a-zA-Z0-9._/-]*', _clean_markdown_cell(cell))
        models = [match.group(0)] if match else []
    return models if '+' in cell else models[:1]

def _cell_efforts(cell: str) -> list[str]:
    efforts = re.findall('`(xhigh|high|medium|low|max|off)`', cell, flags=re.I)
    if not efforts:
        match = re.search('\\b(xhigh|high|medium|low|max|off)\\b', cell, flags=re.I)
        efforts = [match.group(1)] if match else ['']
    return [effort.lower() for effort in efforts]

def _annotated_efforts(cell: str) -> list[tuple[str, set[str]]]:
    return [(match.group(1).lower(), {p.strip().lower() for p in re.split(r"\s*,\s*|\s*;\s*", match.group(2)) if p.strip()})
            for match in re.finditer(r"`?(xhigh|high|medium|low|max|off)`?\s*\(([^)]*)\)", cell, flags=re.I)]

def _model_entries(role: str, cells: list[str], schema: dict[str, int], families: dict[str, str], overrides: dict[str, str]) -> list[ModelEntry]:
    """Согласует парные модели/effort/family и явные аннотации провайдеров."""
    efforts = _cell_efforts(cells[schema['effort']])
    annotations = _annotated_efforts(cells[schema['effort']])
    family_cell = _indexed_cell(cells, schema['family'])
    parts = list(filter(None, (re.sub(r"[`*]", "", p).strip() for p in re.split(r"\s*\+\s*|\s*;\s*", family_cell))))
    fallback = parts[0] if parts else family_cell.strip()
    entries = []
    for i, model in enumerate(_cell_models(cells[schema['model']])):
        if model.lower() in {'модель', 'слот', 'пакет', 'роль', 'local', 'none', '—', '-'}:
            continue
        effort = efforts[i] if i < len(efforts) else efforts[0]
        hint = parts[i] if i < len(parts) else fallback
        family = families.get(model) or hint.strip()
        effort = next((value for value, providers in annotations if family.lower() in providers), overrides.get(model, effort))
        entries.append(ModelEntry(role, model, effort, family))
    return entries

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
    """Маскирует значения секретов до вывода и записи."""
    for name, value in os.environ.items():
        if value and re.search('(?:KEY|TOKEN|SECRET|PASSWORD)$', name, re.I):
            text = text.replace(value, '[REDACTED]')
    return re.sub('((?:Bearer|Basic)\\s+|(?:api[_-]?key|token|secret|password)["\']?\\s*[:=]\\s*["\']?)[^\\s"\'\\\\;,}&]+', '\\1[REDACTED]', text, flags=re.IGNORECASE)

def is_model_limit_error(status_code: int, body: str) -> bool:
    """Распознаёт явный лимит модели в HTTP или структурированной ошибке."""
    if status_code <= 0 or not body:
        return False
    if status_code == 429 or _structured_limit(body):
        return True
    phrases = ("rate limit", "rate_limit", "quota exceeded", "quota_exceeded", "resource_exhausted",
               "resource exhausted", "insufficient_quota", "model_cooldown", "penalized_until",
               "temp_off", "temp off", "blocked_by_limit", "too many requests")
    return status_code in (200, 400, 403, 409, 413, 422) and any(phrase in body.lower() for phrase in phrases)

def _structured_limit(body: str) -> bool:
    """Структурированный тип/код лимита имеет приоритет над HTTP-статусом."""
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return False
    error = parsed.get('error') if isinstance(parsed, dict) else None
    if not isinstance(error, dict):
        return False
    markers = {'rate_limit_error', 'rate_limit_exceeded', 'quota_exceeded', 'resource_exhausted', 'insufficient_quota', 'model_cooldown', 'temp_off', 'blocked_by_limit'}
    return any((str(error.get(key) or '').lower() in markers for key in ('type', 'code')))

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

def smoke_test_model(hub_url: str, model_id: str, *args: Any, **kwargs: Any) -> tuple[bool, str, float]:
    """Проверяет полезный исход с прежними позиционными и keyword опциями."""
    options = _smoke_options(args, kwargs)
    if options.use_subprocess:
        ok, status, latency, _pid = smoke_test_model_subprocess(
            hub_url, model_id, timeout_s=options.timeout_s, api_key=options.api_key,
            effort=options.effort, subagent_id=options.subagent_id,
        )
        return ok, status, float(latency)
    started, key = time.monotonic(), ""
    try:
        key = _resolve_api_key(options.api_key)
        request = _smoke_request(
            hub_url.rstrip("/") + "/chat/completions",
            build_bridge_payload(model_id, effort=options.effort, stream=True),
            key, options.subagent_id or f"smoke-{model_id}",
        )
        row = _request_outcome(request, options.timeout_s)
        return row["useful"], row["status"], float(time.monotonic() - started)
    except ModelLimitException:
        if options.raise_on_limit:
            raise
        return not options.strict_limits, "SKIPPED_LIMIT", float(time.monotonic() - started)
    except Exception as exc:
        return False, _mask_receipt(f"ERROR: {exc}", key), float(time.monotonic() - started)

def _smoke_options(args: tuple[Any, ...], kwargs: dict[str, Any]) -> argparse.Namespace:
    """Связывает старые опции, отклоняя лишние и повторные аргументы."""
    values = dict(timeout_s=20.0, api_key=None, effort='', subagent_id='', use_subprocess=False, strict_limits=False, raise_on_limit=False)
    if len(args) > len(values):
        raise TypeError('too many smoke_test_model arguments')
    positional = dict(zip(values, args))
    if positional.keys() & kwargs.keys() or kwargs.keys() - values.keys():
        raise TypeError('duplicate or unknown smoke_test_model arguments')
    return argparse.Namespace(**values | positional | kwargs)

def _smoke_request(endpoint: str, payload: dict[str, Any], key: str, request_id: str) -> urllib.request.Request:
    """Создаёт запрос; секрет остаётся только в HTTP-заголовке."""
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}', 'X-Subagent-Id': request_id, 'X-Request-Id': request_id}
    return urllib.request.Request(endpoint, data=json.dumps(payload).encode(), method='POST', headers=headers)

def _request_outcome(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    """Читает до EOF; классификацию SSE/JSON полностью выполняет ядро."""
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        code = response.getcode()
        status = code if isinstance(code, int) else 0
        classifier = StreamOutcomeClassifier(status=status, content_type=response.headers.get("Content-Type", "text/event-stream"))
        digest = hashlib.sha256()
        for chunk in response:
            classifier.feed(chunk)
            digest.update(chunk)
        kind = classifier.finish().kind
        if status == 429:
            raise ModelLimitException(f"HTTP {status}", status_code=status)
        return dict(http_status=status, useful=status == 200 and kind is OutcomeKind.OK,
                    status="STREAM_OK" if kind is OutcomeKind.OK else kind.value,
                    body_sha256=digest.hexdigest(), **_observed_attribution(response, request))

def _observed_attribution(response: Any, request: urllib.request.Request) -> dict[str, str]:
    """Не позволяет даже отражённому upstream ключу попасть в receipt."""
    key = str(request.get_header('Authorization', '')).removeprefix('Bearer ')
    fields = {'attempted_backend': 'X-Attempted-Backend', 'canonical_model': 'X-Canonical-Model', 'wire_owned_by': 'X-Wire-Owned-By'}
    return {name: _mask_receipt(str(response.headers.get(header, '')), key) for name, header in fields.items()}

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

def deduplicate_models_for_parallel(entries: list[ModelEntry], all_roles: bool=False) -> list[ModelEntry]:
    """Remove duplicate parallel checks while preserving the first role seen."""
    seen: set[tuple[str, ...]] = set()
    result: list[ModelEntry] = []
    for entry in entries:
        key = (entry.role, entry.model_id, entry.effort.lower()) if all_roles else (entry.model_id, entry.effort.lower())
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
        print(f'USAGE: capability probe unavailable: {exc}', file=sys.stderr)
        return 3
    return int(probe.probe_cli(args.probe_model, provider_id=args.provider or None, hub_url=args.hub_url, force=args.force, as_json=args.as_json, providers_dir=args.providers_dir))

def parse_nfr_number(name: str, raw: Any) -> float:
    """Невалидное значение заменяется default, а не прижимается к границе."""
    bounds = {"BRIDGE_HALF_OPEN_LEASE_TTL_S": (60, 5, 600), "BRIDGE_CATALOG_TTL_S": (60, 5, 600),
              "MODEL_NOTES_REFRESH_INTERVAL_S": (30, 5, 300), "MODEL_NOTES_READ_TIMEOUT_S": (2, 0.01, 10),
              "MODEL_NOTES_STALE_GRACE_S": (60, 0, 60), "CLOCK_SKEW_TOLERANCE_S": (5, 0, 60)}
    default, low, high = bounds[name]
    if isinstance(raw, bool):
        return float(default)
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) and low <= number <= high else float(default)

def load_launch_argv(path: Path, validator: Callable[[list[str]], Any]) -> list[str]:
    """Проверяет JSON argv каноническим preflight, без запуска."""
    argv = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(argv, list) or len(argv) < 3:
        raise ValueError("launch-argv-json must contain a launch_seat argv array")
    if not all(isinstance(arg, str) and arg and "\0" not in arg for arg in argv):
        raise ValueError("launch-argv-json contains invalid arguments")
    if not all((Path(argv[0]).is_absolute(),
                re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", Path(argv[0]).name, re.I),
                Path(argv[1]).is_absolute(), Path(argv[1]).name == "launch_seat.py")):
        raise ValueError("launch-argv-json must invoke absolute launch_seat.py without a shell")
    if validator(argv) is False:
        raise ValueError("canonical launch validation failed")
    return argv

def _valid_request(row: Any) -> bool:
    """Минимум доказательств полезного запроса, без доверия к HTTP 200."""
    if not isinstance(row, dict):
        return False
    return all((row.get("http_status") == 200, row.get("useful") is True, row.get("stream") is False,
                all(isinstance(row.get(key), str) and row[key]
                    for key in ("request_id", "model", "attempted_backend", "trace_ref"))))

def _valid_rows(rows: Any, count: int) -> bool:
    """Проверяет число полезных запросов и уникальность их идентификаторов."""
    if not isinstance(rows, list) or len(rows) != count:
        return False
    if not all((_valid_request(row) for row in rows)):
        return False
    return len({row['request_id'] for row in rows}) == count

def _valid_h2(data: dict[str, Any]) -> bool:
    """H-2 фиксирован спецификацией: двадцать запросов и минимум 12 codex."""
    rows, summary = (data['requests'], data['H-2'])
    if not _valid_rows(rows, 20) or not isinstance(summary, dict):
        return False
    codex = sum((row['attempted_backend'] == 'codex' for row in rows))
    droid = sum((row['attempted_backend'] == 'droid' for row in rows))
    return all((summary == {'n': 20, 'codex_hits': codex, 'droid_hits': droid}, codex >= 12, codex + droid == 20))

def _valid_h2b(data: dict[str, Any]) -> bool:
    """Каждая enabled edge подтверждается отдельным forced запросом."""
    section, edges = data["H-2b"], data["effective_config"]["enabled_edges"]
    rows = section["forced_edges"]
    if set(edges) != {"codex", "droid"} or not _valid_rows(rows, len(edges)):
        return False
    return all(({row.get("forced_backend") for row in rows} == set(edges),
                all(_valid_attribution(row) for row in rows),
                all(section.get(edge + "_status") == "PASS" for edge in edges)))

def _valid_attribution(row: dict[str, Any]) -> bool:
    """Проверяет observed-атрибуцию, не выводя backend из имени модели."""
    return all((row.get("attempted_backend") == row.get("forced_backend"),
                bool(row.get("canonical_model")), row.get("canonical_model") == row.get("expected_canonical_model"),
                bool(row.get("wire_owned_by")), row.get("wire_owned_by") == row.get("expected_wire_owned_by")))

def validate_live_receipt(data: Any) -> bool:
    """Fail-closed: отдельный H-2 не подменяет полную приёмку r9."""
    required = ("run_id revision cab_base skils_base deployed_cab_sha deployed_skils_sha "
                "panel_proof_sha256 council_receipt_sha256 owner_authorization_ref started_at_utc completed_at_utc "
                "hub_url bridge_err_segments commands raw_logs checks_tsv").split()
    try:
        if not all(data.get(key) for key in required):
            return False
        return all((data["schema_version"] == "1.0", data["status"] == "PASS", data["H-0"]["status"] == "PASS",
                    _valid_h2(data), _valid_h2b(data), _receipt_safety(data)))
    except (KeyError, TypeError, AttributeError, ValueError):
        return False

def _receipt_safety(data: dict[str, Any]) -> bool:
    """Независимые H-3/H-6 и отсутствие аварий обязательны для общего PASS."""
    guards, launch = data["H-3"], data["H-6"]
    return all((guards["openai_key_2_hits"] == 0, guards["openai_key_3_hits"] == 0,
                guards["complete_coverage"] is True, launch["launch_rc"] == 0, launch["cli_fallback_rc"] == 0,
                launch["run_id"] == data["run_id"], bool(launch["receipt_ref"]),
                all(command["rc"] == 0 and command["crash_evidence_refs"] == [] for command in data["commands"])))

def _mask_receipt(value: Any, secret: str = "") -> Any:
    """Рекурсивно санитизирует данные до сериализации и файлового write."""
    if isinstance(value, dict):
        return {mask_secret(str(key)): "[REDACTED]"
                if re.fullmatch(r"(?i).*?(?:api[_-]?key|token|secret|password|authorization)", str(key))
                else _mask_receipt(item, secret) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_mask_receipt(item, secret) for item in value]
    if isinstance(value, str):
        masked = mask_secret(value)
        return masked.replace(secret, "[REDACTED]") if secret else masked
    return value

def write_live_receipt(path: Path, data: dict[str, Any]) -> None:
    """Атомарно заменяет receipt только уже маскированным JSON."""
    encoded = json.dumps(_mask_receipt(data), ensure_ascii=False, indent=2) + '\n'
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def _add_harness_arguments(parser: argparse.ArgumentParser) -> None:
    """Настройки H-2/H-2b не меняют обычную матрицу без явного opt-in."""
    parser.add_argument('--run-id', default='')
    parser.add_argument('--v2safe-live-receipt', type=Path)
    parser.add_argument('--launch-argv-json', type=Path)
    parser.add_argument('--launch-validator', default=os.environ.get('SMOKE_LAUNCH_VALIDATOR', ''))
    parser.add_argument('--owner-authorization-ref', default='')
    parser.add_argument('--h2b-model', default=os.environ.get('SMOKE_H2B_MODEL', ''))
    parser.add_argument('--h2b-path', default='/v1/providers/codex/v1/chat/completions')
    parser.add_argument('--h2b-canonical-model', default='')
    parser.add_argument('--h2b-owned-by', default='')
    parser.add_argument('--h2b-peer-model', default='')
    parser.add_argument('--h2b-peer-owned-by', default='')
    parser.add_argument('--h2-model', default=os.environ.get('SMOKE_H2_MODEL', ''))
    parser.add_argument('--bridge-log', type=Path, help='live bridge log for observed request/backend correlation')

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Smoke test runner for models defined in models.md')
    parser.add_argument('--models-md', type=Path, default=DEFAULT_MODELS_MD)
    parser.add_argument('--model-notes-md', type=Path, default=DEFAULT_MODEL_NOTES_MD)
    parser.add_argument('--hub-url', type=str, default=DEFAULT_HUB_URL)
    parser.add_argument('--model', type=str, default='')
    parser.add_argument('--effort', type=str, default='')
    parser.add_argument('--subagent-id', type=str, default='')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--max-workers', type=int, default=None)
    parser.add_argument('--all-roles', action='store_true')
    parser.add_argument('--subprocesses', action='store_true')
    parser.add_argument('--strict-limits', action='store_true')
    parser.add_argument('--worker-single', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--probe-model', type=str, default='', help='run the capability probe (P1..P5) for one canonical model id')
    parser.add_argument('--provider', type=str, default='', help='provider id for --probe-model')
    parser.add_argument('--force', action='store_true', help='re-probe even if confirmed')
    parser.add_argument('--json', dest='as_json', action='store_true')
    parser.add_argument('--providers-dir', type=Path, default=None)
    _add_harness_arguments(parser)
    return parser

def _harness_preflight(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """До сети проверяет разрешение владельца и канонический preflight."""
    if args.v2safe_live_receipt:
        if not args.launch_argv_json or not args.launch_argv_json.is_file():
            parser.error('--v2safe-live-receipt requires existing --launch-argv-json')
        try:
            module, name = args.launch_validator.rsplit(':', 1)
            load_launch_argv(args.launch_argv_json, getattr(importlib.import_module(module), name))
        except (ValueError, OSError, ImportError, AttributeError, argparse.ArgumentError):
            parser.error('--launch-argv-json requires canonical --launch-validator module:callable')
    required = 'run_id owner_authorization_ref h2_model h2b_model h2b_canonical_model h2b_owned_by h2b_peer_model h2b_peer_owned_by'.split()
    if not all((getattr(args, name) for name in required)):
        parser.error('H-2/H-2b require run-id, owner authorization, models and wire attribution')
    path = urlsplit(args.h2b_path)
    if path.scheme or path.netloc or (not re.fullmatch('/v1/providers/[^/]+/v1/chat/completions', args.h2b_path)):
        parser.error('--h2b-path must be a provider-scoped chat/completions path')

def _harness_request(args: argparse.Namespace, model: str, path: str, request_id: str) -> dict[str, Any]:
    """Нестриминговый запрос хранит только исход, атрибуцию и SHA тела."""
    base = urlsplit(args.hub_url)
    endpoint = urlunsplit((base.scheme, base.netloc, path, '', ''))
    payload = build_bridge_payload(model, effort=args.effort, stream=False)
    payload['model'] = model
    request = _smoke_request(endpoint, payload, _resolve_api_key(None), request_id)
    row: dict[str, Any] = dict(request_id=request_id, model=model, stream=False, path=path, trace_ref='request:' + request_id)
    try:
        row.update(_request_outcome(request, args.timeout))
        if args.bridge_log:
            row.update(_logged_attribution(args.bridge_log, request_id))
            if '/providers/' in path:
                row['wire_owned_by'] = _wire_owner(args, model, endpoint)
    except Exception as exc:
        row.update(http_status=0, useful=False, status=type(exc).__name__)
    return _mask_receipt(row, str(request.get_header('Authorization', '')).removeprefix('Bearer '))

def _logged_attribution(path: Path, request_id: str) -> dict[str, str]:
    """Читает bridge.err, не выводя backend из имени или URL."""
    observed: dict[str, str] = {}
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            fields = dict(re.findall('\\b([a-z_]+)=([^\\s]+)', line))
            if request_id not in (fields.get('request_id'), fields.get('subagent_id')):
                continue
            for source, target in (('model', 'canonical_model'), ('backend', 'attempted_backend')):
                if source in fields:
                    observed[target] = fields[source]
    if not all((observed.get(key) for key in ('canonical_model', 'attempted_backend'))):
        raise ValueError('missing correlated bridge attribution')
    return observed

def _wire_owner(args: argparse.Namespace, model: str, endpoint: str) -> str:
    """owned_by берётся из реального provider-scoped /models."""
    endpoint = endpoint.removesuffix('chat/completions') + 'models'
    request = urllib.request.Request(endpoint, headers={'Authorization': f'Bearer {_resolve_api_key(None)}'})
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        if response.getcode() != 200:
            raise ValueError('wire catalog unavailable')
        data = json.load(response)
    matches = [item.get('owned_by', '') for item in data['data'] if item.get('id') == model]
    return str(matches[0]) if len(matches) == 1 else ''

def _run_live_harness(args: argparse.Namespace) -> int:
    """Выполняет H-2/H-2b, не подменяя отсутствующие H-0/H-3/H-6."""
    rows = [_harness_request(args, args.h2_model, "/v1/chat/completions", f"{args.run_id}-h2-{i}") for i in range(20)]
    summary = dict(n=len(rows), codex_hits=sum(row.get("attempted_backend") == "codex" for row in rows),
                   droid_hits=sum(row.get("attempted_backend") == "droid" for row in rows))
    receipt = {"schema_version": "1.0", "run_id": args.run_id, "requests": rows, "H-2": summary,
               "owner_authorization_ref": args.owner_authorization_ref,
               "effective_config": {"enabled_edges": ["codex", "droid"]}, "H-2b": _forced_probes(args),
               "status": "BLOCKED", "not_verified": ["H-0", "H-3", "H-6"]}
    passed = _valid_h2(receipt) and _valid_h2b(receipt)
    receipt["h2_h2b_status"] = "PASS" if passed else "FAIL"
    if args.v2safe_live_receipt:
        write_live_receipt(args.v2safe_live_receipt, receipt)
    print(json.dumps(_mask_receipt(receipt), ensure_ascii=False))
    return 0 if passed else 1

def _forced_probes(args: argparse.Namespace) -> dict[str, Any]:
    """H-2b заставляет обе edges с независимыми ожидаемыми wire owner."""
    primary = args.h2b_path.split('/')[3]
    peer = 'droid' if primary == 'codex' else 'codex'
    cases = ((primary, args.h2b_model, args.h2b_path, args.h2b_owned_by), (peer, args.h2b_peer_model, f'/v1/providers/{peer}/v1/chat/completions', args.h2b_peer_owned_by))
    rows = []
    for backend, model, path, owner in cases:
        row = _harness_request(args, model, path, f'{args.run_id}-h2b-{backend}')
        row.update(forced_backend=backend, expected_canonical_model=args.h2b_canonical_model, expected_wire_owned_by=owner)
        rows.append(row)
    return {'forced_edges': rows, **{row['forced_backend'] + '_status': 'PASS' if _valid_request(row) and _valid_attribution(row) else 'FAIL' for row in rows}}

def main(argv: list[str] | None=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    harness = bool(args.v2safe_live_receipt or args.h2b_model)
    if args.dry_run:
        args.live = args.worker_single = False
        if args.probe_model or harness:
            print('PASS: dry-run; no network requests or launch processes')
            return 0
    if harness and args.live:
        _harness_preflight(args, parser)
        return _run_live_harness(args)
    if args.probe_model:
        return _run_probe_model(args)
    return _run_worker(args) if args.worker_single else _run_matrix(args)

def _run_worker(args: argparse.Namespace) -> int:
    """Сохраняет контракт изолированного worker-single."""
    ok, status, latency = smoke_test_model(args.hub_url, args.model, timeout_s=args.timeout, effort=args.effort, subagent_id=args.subagent_id)
    print(json.dumps(dict(ok=ok, status=status, latency=latency, pgid=os.getpgrp()), ensure_ascii=False), flush=True)
    return 0 if ok else 1

def _run_matrix(args: argparse.Namespace) -> int:
    models = parse_models_md(args.models_md)
    if args.model:
        models = [entry for entry in models if entry.model_id == args.model]
    models = deduplicate_models_for_parallel(models, all_roles=args.all_roles)
    if not models:
        print('FAIL: No models found matching criteria.')
        return 1
    print(f'=== Smoke Models Matrix (Found {len(models)} model entries) ===')
    print(f"{'Role':<24} | {'Model ID':<32} | {'Family':<12} | {'Status':<20} | {'Latency':<10}")
    print('-' * 112)
    return _report_matrix(args, _matrix_results(args, models))

def _matrix_results(args: argparse.Namespace, models: list[ModelEntry]) -> list[dict[str, Any]]:
    """Сухой прогон не вызывает ни HTTP, ни дочерние процессы."""
    if args.live and not args.dry_run:
        return run_parallel_smoke(models, args.hub_url, timeout_s=args.timeout, max_workers=args.max_workers,
                                  use_subprocesses=args.subprocesses,
                                  temp_off_models=parse_temp_off_models(args.model_notes_md), strict_limits=args.strict_limits)
    return [dict(role=e.role, model_id=e.model_id, family=e.family, ok=True, status="CONFIGURED", latency=0.0) for e in models]

def _report_matrix(args: argparse.Namespace, results: list[dict[str, Any]]) -> int:
    """Печатает прежнюю матрицу и возвращает её итоговый код."""
    for result in results:
        latency = f"{result['latency']:.2f}s" if args.live else '-'
        print(f"{result['role']:<24} | {result['model_id']:<32} | {result['family']:<12} | {result['status']:<20} | {latency:<10}")
    if args.dry_run:
        print('\nPASS: Configuration is valid (dry-run mode).')
        return 0
    if not args.live:
        print('\nNOTE: Run with --live to perform actual network requests.')
        return 0
    return _matrix_exit_code(results)

def _matrix_exit_code(results: list[dict[str, Any]]) -> int:
    """Считает статусы отдельно от представления матрицы."""
    stream_ok_count = sum((result.get('status') in ('STREAM_OK', 'DONE_OK') for result in results))
    skipped_limit_count = sum((result.get('status') == 'SKIPPED_LIMIT' for result in results))
    print(f'\nSUMMARY: total={len(results)} stream_ok={stream_ok_count} skipped_limit={skipped_limit_count}')
    if results and stream_ok_count == 0:
        return 1
    return 0 if all((bool(result['ok']) for result in results)) else 1

if __name__ == "__main__":
    sys.exit(main())

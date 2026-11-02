#!/usr/bin/env python3
"""scripts/smoke_models.py — Универсальный смоук-раннер моделей по models.md (L3)

Позволяет автоматически проверять доступность и работоспособность моделей из
канонического файла ~/Мой диск/Context/models.md через мост-шлюз cli-agent-bridge.

Использование:
    python3 scripts/smoke_models.py --dry-run
    python3 scripts/smoke_models.py --live --hub-url http://127.0.0.1:9882/v1
    python3 scripts/smoke_models.py --live --model claude-sonnet-5-5
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, NamedTuple


DEFAULT_MODELS_MD = Path(
    os.environ.get("MODELS_MD_PATH") or "~/Мой диск/Context/models.md"
).expanduser()
DEFAULT_HUB_URL = os.environ.get("HUB_BRIDGE_URL", "http://127.0.0.1:9882/v1")


class ModelEntry(NamedTuple):
    role: str
    model_id: str
    effort: str
    family: str


def parse_models_md(path: Path) -> list[ModelEntry]:
    """Извлечь уникальные модели и роли из models.md."""
    if not path.is_file():
        raise FileNotFoundError(f"Канонический файл models.md не найден: {path}")

    content = path.read_text(encoding="utf-8")
    entries: list[ModelEntry] = []
    current_role = "General"

    # Регулярное выражение для строк вида:
    # | `claude-sonnet-5-5` | `high` | Anthropic | ... |
    row_pattern = re.compile(
        r"^\|\s*`?([a-zA-Z0-9.\-_]+)`?\s*\|\s*`?([a-zA-Z0-9]+)`?\s*\|\s*([a-zA-Z0-9.\s]+)\s*\|"
    )

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("### "):
            header = line[4:].strip()
            # Извлекаем роль из заголовка (например "### Coder — пул разработки...")
            current_role = header.split("—")[0].split("-")[0].strip()
            continue

        match = row_pattern.match(line)
        if match:
            model_id = match.group(1).strip()
            effort = match.group(2).strip()
            family = match.group(3).strip()
            # Пропускаем заголовки таблиц
            if model_id.lower() in ("модель", "слот", "пакет", "№", "роль"):
                continue
            entries.append(ModelEntry(current_role, model_id, effort, family))

    # Дедупликация по паре (role, model_id)
    seen = set()
    unique_entries = []
    for e in entries:
        key = (e.role, e.model_id)
        if key not in seen:
            seen.add(key)
            unique_entries.append(e)

    return unique_entries


def mask_secret(text: str) -> str:
    """Маскирование токенов и авторизационных заголовков."""
    return re.sub(
        r"(Bearer\s+|api[_-]?key[:=]\s*)[a-zA-Z0-9_\-\.]{8,}",
        r"\1[MASKED]",
        text,
        flags=re.IGNORECASE,
    )


def smoke_test_model(
    hub_url: str,
    model_id: str,
    timeout_s: float = 20.0,
    api_key: str | None = None,
) -> tuple[bool, str, float]:
    """Выполнить смоук-запрос к модели через OpenAI-совместимый SSE-стрим с замером TTFT."""
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
    if not key:
        key = os.environ.get("OPENAI_API_KEY") or "test-smoke-key"

    endpoint = hub_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 15,
        "stream": True,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")

    t0 = time.monotonic()
    ttft: float | None = None
    got_done = False
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status_code = resp.getcode()
            if status_code != 200:
                return False, f"HTTP {status_code}", time.monotonic() - t0
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    got_done = True
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        if (
                            delta.get("content")
                            or delta.get("reasoning_content")
                            or delta.get("thinking")
                        ):
                            if ttft is None:
                                ttft = time.monotonic() - t0
                except ValueError:
                    pass
            elapsed = time.monotonic() - t0
            display_time = ttft if ttft is not None else elapsed
            if ttft is not None:
                return True, "STREAM_OK", display_time
            if got_done:
                return True, "DONE_OK", elapsed
            return False, "No stream chunks", elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.monotonic() - t0
        err_msg = mask_secret(f"HTTP {e.code}: {e.reason}")
        return False, err_msg, elapsed
    except Exception as e:
        elapsed = time.monotonic() - t0
        return False, mask_secret(f"Error: {e}"), elapsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test runner for models defined in models.md"
    )
    parser.add_argument(
        "--models-md",
        type=Path,
        default=DEFAULT_MODELS_MD,
        help="Path to Context/models.md",
    )
    parser.add_argument(
        "--hub-url",
        type=str,
        default=DEFAULT_HUB_URL,
        help="URL of the bridge hub endpoint",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="",
        help="Filter by specific model ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and parse models without sending network requests",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute live HTTP smoke requests against the hub",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Request timeout in seconds",
    )

    args = parser.parse_args()

    models = parse_models_md(args.models_md)
    if args.model:
        models = [m for m in models if m.model_id == args.model]

    if not models:
        print("FAIL: No models found matching criteria.")
        return 1

    print(f"=== Smoke Models Matrix (Found {len(models)} model entries) ===")
    print(f"{'Role':<15} | {'Model ID':<25} | {'Family':<15} | {'Status':<15} | {'Latency':<10}")
    print("-" * 88)

    all_ok = True
    for entry in models:
        if args.dry_run or not args.live:
            status = "CONFIGURED"
            latency_str = "-"
        else:
            ok, status, lat = smoke_test_model(
                args.hub_url, entry.model_id, timeout_s=args.timeout
            )
            latency_str = f"{lat:.2f}s"
            if not ok:
                all_ok = False

        print(
            f"{entry.role:<15} | {entry.model_id:<25} | {entry.family:<15} | {status:<15} | {latency_str:<10}"
        )

    if args.dry_run:
        print("\nPASS: Configuration is valid (dry-run mode).")
        return 0

    if not args.live:
        print("\nNOTE: Run with --live to perform actual network requests, or --dry-run for validation.")
        return 0

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

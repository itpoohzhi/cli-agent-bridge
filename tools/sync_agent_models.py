#!/usr/bin/env python3
"""Синхронизация каталогов моделей cli-agent-bridge в локальные JSON-файлы по провайдерам."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROVIDERS = ("claude-code", "codex", "agy", "muse", "opencode")
DEFAULT_BASE_URL = "http://127.0.0.1:9882"
DEFAULT_OUT_DIR = "~/.config/cli-agent-bridge/models"
HERMES_CONFIG_PATH = Path("~/.hermes/config.yaml").expanduser()
BACKUP_DIR = Path("~/work/backups").expanduser()
MAX_BACKUPS = 10

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_HERMES = 2
EXIT_UPSTREAM = 3


def _call(url: str, key: str, method: str = "GET", etag: str | None = None, timeout: float = 15.0) -> tuple[int, Any, bytes]:
    request = urllib.request.Request(
        url, method=method, data=b"" if method == "POST" else None
    )
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    if etag:
        request.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return 304, exc.headers, b""
        raise


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.with_name(path.name + ".lock")
    with open(lock_file, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    json.dump(data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
                    tmp.write("\n")
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(tmp_name, path)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def sync_provider(base_url: str, key: str, provider: str, out_dir: Path, force: bool = False, timeout: float = 15.0) -> str:
    """Возвращает 'updated' или 'unchanged'."""
    target = out_dir / f"{provider}.json"
    cached_etag = None if force else _read_cache(target).get("etag")
    url = f"{base_url}/v1/providers/{provider}/v1/models"
    status, headers, body = _call(url, key, etag=cached_etag, timeout=timeout)
    if status == 304:
        return "unchanged"
    payload = json.loads(body)
    models = payload.get("data")
    if not isinstance(models, list):
        raise ValueError(f"{url}: в ответе нет списка data")
    _write_atomic(
        target,
        {"provider": provider, "etag": headers.get("ETag"), "models": models},
    )
    return "updated"


def refresh_models(base_url: str, key: str, timeout: float = 15.0) -> None:
    if not key:
        print("ERROR: для --refresh нужна переменная окружения BRIDGE_KEY", file=sys.stderr)
        sys.exit(EXIT_UPSTREAM)
    try:
        _call(f"{base_url}/v1/models/refresh", key, method="POST", timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry = exc.headers.get("Retry-After", "10")
            print(f"refresh пропущен: rate limit, повторить через {retry}с", file=sys.stderr)
            raise
        print(f"refresh ошибка: HTTP {exc.code}", file=sys.stderr)
        raise


def clear_hermes_cache() -> bool:
    """Сбрасывает дисковый кеш Hermes Desktop."""
    cache_path = Path("~/.hermes/provider_models_cache.json").expanduser()
    if cache_path.exists():
        try:
            cache_path.unlink()
            print(f"Hermes cache cleared: {cache_path}")
            return True
        except OSError as e:
            print(f"Failed to unlink {cache_path}: {e}", file=sys.stderr)
            return False
    return True


def rotate_backups() -> None:
    """Ротация бэкапов: оставляет не более MAX_BACKUPS файлов."""
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("hermes-config.yaml.*.bak"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-MAX_BACKUPS]:
        old.unlink(missing_ok=True)


def backup_hermes_config() -> None:
    """Создаёт ротируемый бэкап config.yaml в ~/work/backups/."""
    if not HERMES_CONFIG_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"hermes-config.yaml.{ts}.bak"
    shutil.copy2(HERMES_CONFIG_PATH, backup_file)
    os.chmod(backup_file, 0o600)
    rotate_backups()
    print(f"Backup created: {backup_file}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("BRIDGE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--provider", action="append", choices=PROVIDERS,
        help="провайдер (можно несколько раз); по умолчанию все",
    )
    parser.add_argument("--refresh", action="store_true",
                        help="перед синхронизацией дёрнуть POST /v1/models/refresh")
    parser.add_argument("--clear-hermes-cache", action="store_true",
                        help="сбросить дисковый кеш Hermes Desktop")
    parser.add_argument("--force", action="store_true", help="игнорировать сохранённый ETag")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    key = os.environ.get("BRIDGE_KEY", "")
    if not key and os.path.exists(os.path.expanduser("~/.dsh/.env")):
        with open(os.path.expanduser("~/.dsh/.env")) as f:
            for line in f:
                if line.startswith(("DROID_DSH_BRIDGE_KEY=", "BRIDGE_KEY=")):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break

    base_url = args.base_url.rstrip("/")
    out_dir = Path(args.out_dir).expanduser()

    if args.refresh:
        try:
            refresh_models(base_url, key, args.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                return EXIT_UPSTREAM
            return EXIT_UPSTREAM
        except (urllib.error.URLError, OSError) as exc:
            print(f"refresh: ошибка: {exc}", file=sys.stderr)
            return EXIT_UPSTREAM

    if args.clear_hermes_cache:
        backup_hermes_config()
        if not clear_hermes_cache():
            return EXIT_HERMES

    failed = 0
    for provider in args.provider or PROVIDERS:
        try:
            result = sync_provider(base_url, key, provider, out_dir, args.force, args.timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failed += 1
            print(f"{provider}: ошибка: {exc}", file=sys.stderr)
            continue
        print(f"{provider}: {result} -> {out_dir / (provider + '.json')}")
    return EXIT_FAIL if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

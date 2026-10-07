#!/usr/bin/env python3
"""DEP-09: квалифицированный неизменяемый образ droid и receipt допуска (AD-010, RW-007).

Копирует исполняемый файл droid в `workspace/runtime/droid-image/<sha256>/droid`
(каталог 0700, файл 0500; sha256 считается по КОПИИ после fsync), глобальный бинарь не
меняет. Затем атомарно пишет `workspace/state/droid-binary-receipt.json` (schema 1):
мост на каждом spawn читает receipt и запускает droid только как DROID_BIN=<образ>.
Предыдущие образы остаются на диске (откат — вернуть прежний receipt).

Квалификация (стенд, malicious-tool probe) выполняется отдельным шагом ДО записи receipt:
этот инструмент лишь фиксирует образ, уже допущенный владельцем; боевой профиль DSH не трогает.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def install_image(source: Path, workspace: Path) -> dict:
    """Скопировать образ, записать receipt; вернуть содержимое receipt."""
    snapshot = source.stat()
    source_sha = _sha256(source)
    runtime = workspace / "runtime" / "droid-image"
    runtime.mkdir(parents=True, exist_ok=True)
    tmp = runtime / f".incoming-{os.getpid()}"
    shutil.copyfile(source, tmp)
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    image_sha = _sha256(tmp)
    image_dir = runtime / image_sha
    image_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(image_dir, 0o700)
    image = image_dir / "droid"
    if image.exists():
        os.chmod(image, 0o700)
    os.replace(tmp, image)
    os.chmod(image, 0o500)
    receipt = {
        "schema": 1, "image_path": str(image), "image_sha256": image_sha,
        "source": {"path": str(source), "mtime_ns": snapshot.st_mtime_ns,
                   "size": snapshot.st_size, "sha256": source_sha},
        "created_at": int(time.time()),
    }
    state = workspace / "state"
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = state / "droid-binary-receipt.json"
    staging = state / f".receipt-{os.getpid()}.tmp"
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staging, target)
    return receipt


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(prog="droid_image", description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=os.path.expanduser("~/.local/bin/droid"),
                        help="глобальный бинарь droid (не изменяется)")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parent.parent / "workspace"),
                        help="workspace моста (runtime/droid-image и state/)")
    args = parser.parse_args(argv)
    source = Path(args.source)
    if not source.is_file() or not os.access(source, os.X_OK):
        sys.stderr.write(f"droid_image: источник не найден или не исполняем: {source}\n")
        return 2
    receipt = install_image(source, Path(args.workspace))
    sys.stdout.write(f"image={receipt['image_path']} sha256={receipt['image_sha256']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

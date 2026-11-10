#!/usr/bin/env python3
"""Безопасная ротация .ai-team/runs; без --apply файлы не удаляются.

Настройки берутся только из окружения: AI_TEAM_ROOT (по умолчанию
<репозиторий>/.ai-team), AI_TEAM_RUNS_TTL_DAYS (14 дней),
AI_TEAM_RUNS_MAX_GB (10 ГиБ). Возраст определяется по mtime каталога.
Размер — сумма логических размеров обычных файлов, без перехода по ссылкам.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import shutil
import stat
import sys
import time


@dataclass
class Run:
    """Сведения о каталоге прогона на момент обхода."""

    path: Path
    size: int
    mtime: float


def read_limit(name: str, default: str) -> float:
    """Прочитать конечное неотрицательное число из окружения."""
    try:
        value = float(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name}: требуется неотрицательное число") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name}: требуется конечное неотрицательное число")
    return value


def run_size(path: Path) -> int:
    """Посчитать размеры файлов, не следуя символическим ссылкам."""
    total = 0

    def fail(error: OSError) -> None:
        """Не допускать неполного подсчёта при ошибках чтения."""
        raise error

    for directory, _, filenames in os.walk(path, followlinks=False, onerror=fail):
        for filename in filenames:
            info = (Path(directory) / filename).lstat()
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def collect_runs(root: Path) -> list[Run]:
    """Собрать только настоящие каталоги, отказавшись от ссылки runs."""
    runs = root / "runs"
    if runs.is_symlink():
        raise ValueError("каталог runs не должен быть символической ссылкой")
    if not runs.exists():
        return []
    result: list[Run] = []
    for path in runs.iterdir():
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            result.append(Run(path, run_size(path), info.st_mtime))
    return sorted(result, key=lambda run: (run.mtime, run.path.name))


def active_mentions(root: Path, slug: str) -> bool:
    """Искать slug во всём YAML-тексте; лишняя защита безопаснее удаления.

    YAML не разбирается: упоминания в путях и комментариях тоже защищают прогон.
    Ошибки чтения прерывают ротацию, а не снимают защиту.
    """
    active = root / "active"
    if not active.exists():
        return False
    return any(
        slug in path.read_text(encoding="utf-8") for path in active.glob("*.yaml")
    )


class Options(argparse.Namespace):
    """Типизированные переключатели CLI без эксплуатационных параметров."""

    apply: bool = False


def main() -> int:
    """Проверить настройки и вывести безопасный план ротации."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    _ = mode.add_argument("--dry-run", action="store_true", help="только показать план")
    _ = mode.add_argument(
        "--apply", action="store_true", help="удалить выбранные каталоги"
    )
    args = Options()
    _ = parser.parse_args(namespace=args)
    dry_run = not args.apply
    try:
        ttl_days = read_limit("AI_TEAM_RUNS_TTL_DAYS", "14")
        max_bytes = read_limit("AI_TEAM_RUNS_MAX_GB", "10") * 1024**3
        root = Path(
            os.environ.get(
                "AI_TEAM_ROOT", str(Path(__file__).resolve().parents[1] / ".ai-team")
            )
        ).expanduser()
        runs = collect_runs(root)
        now = time.time()
        total = sum(run.size for run in runs)
        remaining = total
        selected: set[str] = set()
        protected = {
            run.path.name for run in runs if active_mentions(root, run.path.name)
        }
        # Сначала TTL; бюджет учитывает уже выбранные каталоги и активные прогоны.
        for run in runs:
            if run.path.name not in protected and (now - run.mtime) / 86400 > ttl_days:
                selected.add(run.path.name)
                remaining -= run.size
        for run in runs:
            if remaining <= max_bytes:
                break
            if run.path.name not in protected and run.path.name not in selected:
                selected.add(run.path.name)
                remaining -= run.size
        candidates = deleted = freed = 0
        for run in runs:
            age = max(0.0, (now - run.mtime) / 86400)
            # Перечитать защиту прямо перед удалением: прогон мог стать активным.
            if run.path.name in protected or active_mentions(root, run.path.name):
                action = "skipped_active"
            elif run.path.name in selected:
                candidates += 1
                action = "would_delete"
                if not dry_run:
                    shutil.rmtree(run.path)
                    deleted += 1
                    freed += run.size
                    action = "deleted"
            else:
                action = "skipped_fresh"
            print(
                f"slug={run.path.name} размер_миб={run.size / 1024**2:.2f} возраст_дней={age:.2f} действие={action}"
            )
        print(
            f"prune_ai_team: candidates={candidates} deleted={deleted} freed_mib={freed / 1024**2:.2f} kept_mib={(total - freed) / 1024**2:.2f} dry_run={str(dry_run).lower()}"
        )
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"prune_ai_team: ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

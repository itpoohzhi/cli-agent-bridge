"""Проверки безопасной ротации на временных каталогах."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "prune_ai_team.py"
MIB = 1024**2


@pytest.fixture
def team_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Изолировать все настройки и данные от настоящего .ai-team."""
    root = tmp_path / ".ai-team"
    (root / "runs").mkdir(parents=True)
    (root / "active").mkdir()
    monkeypatch.setenv("AI_TEAM_ROOT", str(root))
    monkeypatch.setenv("AI_TEAM_RUNS_TTL_DAYS", "14")
    monkeypatch.setenv("AI_TEAM_RUNS_MAX_GB", "10")
    return root


def make_run(root: Path, slug: str, age_days: float, size: int = 1024) -> Path:
    """Создать артефакт заданного размера и состарить каталог."""
    run = root / "runs" / slug
    run.mkdir()
    _ = (run / "artifact.bin").write_bytes(b"x" * size)
    timestamp = time.time() - age_days * 86400
    os.utime(run, (timestamp, timestamp))
    return run


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Вызвать настоящий CLI без сети и оболочки."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


@pytest.mark.parametrize("args", [(), ("--dry-run",)])
def test_dry_run_keeps_old_directory(team_root: Path, args: tuple[str, ...]) -> None:
    """Неявный и явный dry-run сохраняют файлы и показывают план."""
    run = make_run(team_root, "old-run", 30)
    result = run_cli(*args)

    assert run.is_dir()
    assert (run / "artifact.bin").read_bytes() == b"x" * 1024
    assert "old-run" in result.stdout
    assert "would_delete" in result.stdout
    assert "candidates=1 deleted=0 freed_mib=0.00" in result.stdout
    assert "dry_run=true" in result.stdout


@pytest.mark.parametrize("args", [(), ("--apply",)])
@pytest.mark.parametrize(
    "reference",
    ["slug: active-old\n", "run_path: .ai-team/runs/active-old\n", "# active-old\n"],
)
def test_active_old_directory_is_protected(
    team_root: Path, args: tuple[str, ...], reference: str
) -> None:
    """Любое упоминание slug в любом YAML защищает даже старый прогон."""
    run = make_run(team_root, "active-old", 30)
    _ = (team_root / "active" / "unrelated.yaml").write_text(
        "slug: other\n", encoding="utf-8"
    )
    _ = (team_root / "active" / "worker.yaml").write_text(reference, encoding="utf-8")
    result = run_cli(*args)

    assert run.is_dir()
    assert "skipped_active" in result.stdout
    assert "would_delete" not in result.stdout
    assert "candidates=0 deleted=0" in result.stdout


def test_apply_removes_old_directory(team_root: Path) -> None:
    """Apply удаляет старый каталог, сохраняя свежий."""
    old = make_run(team_root, "old-run", 20, size=MIB)
    fresh = make_run(team_root, "fresh-run", 1)
    result = run_cli("--apply")

    assert not old.exists()
    assert fresh.is_dir()
    assert "skipped_fresh" in result.stdout
    assert "действие=deleted" in result.stdout
    assert "candidates=1 deleted=1 freed_mib=1.00" in result.stdout
    assert "dry_run=false" in result.stdout


@pytest.mark.parametrize("args", [(), ("--apply",)])
def test_size_limit_removes_oldest_and_keeps_fresh(
    team_root: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]
) -> None:
    """Бюджет удаляет только самые старые, dry-run симулирует тот же выбор."""
    monkeypatch.setenv("AI_TEAM_RUNS_MAX_GB", str(2 / 1024))
    oldest = make_run(team_root, "oldest", 10, size=MIB)
    middle = make_run(team_root, "middle", 5, size=MIB)
    fresh = make_run(team_root, "fresh", 1, size=MIB)
    result = run_cli(*args)

    assert oldest.exists() == (not args)
    assert middle.is_dir()
    assert fresh.is_dir()
    expected = "deleted" if args else "would_delete"
    assert (
        f"slug=oldest размер_миб=1.00 возраст_дней=10.00 действие={expected}"
        in result.stdout
    )
    assert "candidates=1" in result.stdout


def test_ttl_precedes_size_limit(
    team_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Удалённое по TTL уже учтено при проверке бюджета."""
    monkeypatch.setenv("AI_TEAM_RUNS_MAX_GB", str(1 / 1024))
    old = make_run(team_root, "old", 30, size=MIB)
    fresh = make_run(team_root, "fresh", 1, size=MIB)
    result = run_cli("--apply")

    assert not old.exists()
    assert fresh.is_dir()
    assert "candidates=1 deleted=1 freed_mib=1.00 kept_mib=1.00" in result.stdout


def test_active_survives_even_when_limit_is_unreachable(
    team_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Активный каталог неприкосновенен даже при нулевом бюджете."""
    monkeypatch.setenv("AI_TEAM_RUNS_MAX_GB", "0")
    active = make_run(team_root, "active", 30, size=MIB)
    other = make_run(team_root, "other", 1, size=MIB)
    _ = (team_root / "active" / "worker.yaml").write_text(
        "slug: active\n", encoding="utf-8"
    )
    result = run_cli("--apply")

    assert active.is_dir()
    assert not other.exists()
    assert "skipped_active" in result.stdout
    assert "kept_mib=1.00" in result.stdout


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "invalid"])
@pytest.mark.parametrize("name", ["AI_TEAM_RUNS_TTL_DAYS", "AI_TEAM_RUNS_MAX_GB"])
def test_invalid_limits_fail_without_deletion(
    team_root: Path, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    """Ошибочные настройки не приводят к удалению."""
    old = make_run(team_root, "old", 30)
    monkeypatch.setenv(name, value)
    result = run_cli("--apply", check=False)

    assert result.returncode == 1
    assert old.is_dir()
    assert "ошибка" in result.stderr


def test_unreadable_active_metadata_fails_closed(team_root: Path) -> None:
    """Нечитаемый YAML не снимает защиту активных прогонов."""
    old = make_run(team_root, "old", 30)
    _ = (team_root / "active" / "broken.yaml").write_bytes(b"\xff")
    result = run_cli("--apply", check=False)

    assert result.returncode == 1
    assert old.is_dir()


def test_symlinks_are_not_followed(team_root: Path, tmp_path: Path) -> None:
    """Не обходить внешние каталоги и не удалять цели ссылок."""
    external = tmp_path / "external"
    external.mkdir()
    artifact = external / "keep.bin"
    _ = artifact.write_bytes(b"keep")
    run = make_run(team_root, "old", 30)
    (run / "linked-dir").symlink_to(external, target_is_directory=True)
    (run / "linked-file").symlink_to(artifact)
    (team_root / "runs" / "linked-run").symlink_to(external, target_is_directory=True)
    timestamp = time.time() - 30 * 86400
    os.utime(run, (timestamp, timestamp))
    result = run_cli("--apply")

    assert not run.exists()
    assert artifact.read_bytes() == b"keep"
    assert (team_root / "runs" / "linked-run").is_symlink()
    assert "slug=linked-run" not in result.stdout


def test_missing_runs_is_noop(team_root: Path) -> None:
    """Отсутствующий runs не является ошибкой и не создаётся."""
    (team_root / "runs").rmdir()
    result = run_cli("--apply")

    assert "candidates=0 deleted=0 freed_mib=0.00 kept_mib=0.00" in result.stdout
    assert not (team_root / "runs").exists()

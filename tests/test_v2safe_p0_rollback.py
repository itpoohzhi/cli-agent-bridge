from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import shutil
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = REPO_ROOT / ".ai-team/runs/tv2safe-20261116/p0-commit-ledger.json"
EXPECTED_BASE = "5ecd42a181c6e7217471659e75e008ab18355da7"
EXPECTED_COMMITS = [
    ("C2-8", "0b48ba2830ed105aff44bbd6553d6b8877ff87f0"),
    ("C2-9", "44bbc8a1c1e5542f2e642bce1c98374b3d16d117"),
    ("C2-10", "6509a6ec8e04f01cbd784d3099609df9c5236953"),
    ("C2-8b", "9715f977cc9117e002f51f150852d29be5cf5a40"),
    ("C2-8c", "7ed6a9cf0662485823231fa545921cbe434e2544"),
    ("C2-8d", "447a53a51be9b7a76351805a9e3227816cd90717"),
    ("C2-8e", "293d9ef92c5c90f4b838fef76bafc1483db61064"),
    ("C2-8f", "5e918233300b8c9b69b1a8df5e4ba9e5d3cb2d89"),
    ("C2-8g", "80b3b9715be85cfb1f30966527c5208370a2c256"),
    ("C2-11", "0d4590e84c1712f823301c868904fa9c038b78c9"),
]


def _git(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )


def _load_ledger() -> dict[str, Any]:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    assert isinstance(ledger, dict)
    assert set(ledger) == {"run_id", "slice", "base", "commit_count", "commits"}
    assert ledger["run_id"] == "tv2safe-20261116"
    assert ledger["slice"] == "P0"
    assert ledger["base"] == EXPECTED_BASE
    assert ledger["commit_count"] == 10
    assert isinstance(ledger["commits"], list)
    return ledger


def _validate_commit_entries(commits: list[dict[str, Any]]) -> None:
    assert len(commits) == 10
    actual = []
    for commit in commits:
        assert set(commit) == {"wave", "sha", "title"}
        assert all(isinstance(commit[key], str) for key in commit)
        assert commit["title"]
        actual.append((commit["wave"], commit["sha"]))
    assert actual == EXPECTED_COMMITS


def _trailers(sha: str) -> dict[str, str]:
    result = _git("show", "-s", "--format=%(trailers:only,unfold)", sha)
    assert result.returncode == 0, result.stderr
    return dict(line.split(": ", 1) for line in result.stdout.splitlines() if ": " in line)


def test_p0_commit_ledger_matches_git_log() -> None:
    ledger = _load_ledger()
    commits = ledger["commits"]
    _validate_commit_entries(commits)

    result = _git("log", "--reverse", "--format=%H", f"{EXPECTED_BASE}..HEAD")
    assert result.returncode == 0, result.stderr
    log_shas = result.stdout.splitlines()
    ledger_shas = [commit["sha"] for commit in commits]
    assert all(sha in log_shas for sha in ledger_shas)
    assert [log_shas.index(sha) for sha in ledger_shas] == sorted(
        log_shas.index(sha) for sha in ledger_shas
    )

    for commit in commits:
        trailers = _trailers(commit["sha"])
        assert trailers.get("V2Safe-Slice") == "P0"
        assert trailers.get("V2Safe-Wave") == commit["wave"]


def test_p0_disposable_worktree_reverse_revert(tmp_path: Path) -> None:
    commits = _load_ledger()["commits"]
    _validate_commit_entries(commits)
    original_head = _git("rev-parse", "HEAD").stdout.strip()
    original_status = _git("status", "-s").stdout
    controller = tmp_path / "controller"
    worktree = tmp_path / "p0-reverse-revert"

    try:
        cloned = _git(
            "clone",
            "--shared",
            "--no-checkout",
            str(REPO_ROOT),
            str(controller),
            cwd=tmp_path,
        )
        assert cloned.returncode == 0, cloned.stderr
        added = _git(
            "worktree", "add", "--detach", str(worktree), "HEAD", cwd=controller
        )
        assert added.returncode == 0, added.stderr
        for commit in reversed(commits):
            reverted = _git("revert", "--no-commit", commit["sha"], cwd=worktree)
            assert reverted.returncode == 0, (
                f"revert failed for {commit['wave']} ({commit['sha']}):\n"
                f"{reverted.stdout}{reverted.stderr}"
            )
    finally:
        _git("worktree", "remove", "--force", str(worktree), cwd=controller)
        shutil.rmtree(worktree, ignore_errors=True)
        shutil.rmtree(controller, ignore_errors=True)

    assert _git("rev-parse", "HEAD").stdout.strip() == original_head
    assert _git("status", "-s").stdout == original_status

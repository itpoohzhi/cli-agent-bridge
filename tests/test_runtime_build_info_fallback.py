"""L1: цепочка `git_head_sha` (AD-009, VER-014): git(repo_root) → git(core) → env → unknown.

Реального git/subprocess нет: `subprocess.run` модуля подменяется; env — только monkeypatch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import core.runtime_build_info as rbi  # noqa: E402

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_ENV = "c" * 40


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(rbi.GIT_SHA_ENV, raising=False)
    monkeypatch.delenv(rbi.GIT_TIMEOUT_ENV, raising=False)


class _FakeGit:
    """Подмена `subprocess.run`: ответ по каталогу из аргумента `-C`."""

    def __init__(self, answers: dict[str, object]) -> None:
        self.answers = answers
        self.calls: list[str] = []
        self.timeouts: list[object] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> SimpleNamespace:
        root = cmd[cmd.index("-C") + 1]
        self.calls.append(root)
        self.timeouts.append(kwargs.get("timeout"))
        answer = self.answers.get(root)
        if isinstance(answer, BaseException):
            raise answer
        if answer is None:
            return SimpleNamespace(returncode=128, stdout="")
        return SimpleNamespace(returncode=0, stdout=f"{answer}\n")


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answers: dict[str, object]) -> _FakeGit:
    core_dir = tmp_path / "core_real"
    monkeypatch.setattr(rbi, "_core_package_dir", lambda: core_dir)
    fake = _FakeGit({str(k): v for k, v in answers.items()})
    monkeypatch.setattr(rbi.subprocess, "run", fake)
    return fake


def test_repo_root_wins_and_core_is_not_queried(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    fake = _install(monkeypatch, tmp_path, {repo: _SHA_A, tmp_path / "core_real": _SHA_B})
    assert rbi.resolve_git_head_sha(repo) == _SHA_A
    assert fake.calls == [str(repo)]


def test_falls_back_to_realpath_core_when_repo_root_is_not_git(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _install(monkeypatch, tmp_path, {tmp_path / "core_real": _SHA_B})
    assert rbi.resolve_git_head_sha(tmp_path / "repo") == _SHA_B
    assert fake.calls == [str(tmp_path / "repo"), str(tmp_path / "core_real")]


def test_falls_back_to_env_when_both_git_probes_fail(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = _install(monkeypatch, tmp_path, {})
    monkeypatch.setenv(rbi.GIT_SHA_ENV, _SHA_ENV.upper())
    assert rbi.resolve_git_head_sha(tmp_path / "repo") == _SHA_ENV


@pytest.mark.parametrize("value", ["", "unknown", "xyz", "a" * 39, "g" * 40, "a" * 41])
def test_invalid_env_sha_yields_unknown(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str) -> None:
    _ = _install(monkeypatch, tmp_path, {})
    monkeypatch.setenv(rbi.GIT_SHA_ENV, value)
    assert rbi.resolve_git_head_sha(tmp_path / "repo") == rbi.UNKNOWN


def test_env_mapping_argument_overrides_process_env(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = _install(monkeypatch, tmp_path, {})
    monkeypatch.setenv(rbi.GIT_SHA_ENV, _SHA_A)
    assert rbi.resolve_git_head_sha(tmp_path, {rbi.GIT_SHA_ENV: _SHA_B}) == _SHA_B
    assert rbi.resolve_git_head_sha(tmp_path, {}) == rbi.UNKNOWN


@pytest.mark.parametrize("error", [OSError("no git"), subprocess.TimeoutExpired("git", 2.0), subprocess.SubprocessError("x")])
def test_subprocess_errors_degrade_to_next_source(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: BaseException) -> None:
    repo = tmp_path / "repo"
    _ = _install(monkeypatch, tmp_path, {repo: error, tmp_path / "core_real": error})
    assert rbi.resolve_git_head_sha(repo, {}) == rbi.UNKNOWN


def test_malformed_git_output_is_unknown(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _ = _install(monkeypatch, tmp_path, {repo: "not-a-sha", tmp_path / "core_real": "HEAD detached"})
    assert rbi.resolve_git_head_sha(repo, {}) == rbi.UNKNOWN


def test_sha256_object_format_is_accepted(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _ = _install(monkeypatch, tmp_path, {repo: "d" * 64})
    assert rbi.resolve_git_head_sha(repo) == "d" * 64


def test_git_output_is_normalized_to_lowercase(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _ = _install(monkeypatch, tmp_path, {repo: "AB" * 20})
    assert rbi.resolve_git_head_sha(repo) == "ab" * 20


def test_timeout_comes_from_existing_env(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    fake = _install(monkeypatch, tmp_path, {repo: _SHA_A})
    monkeypatch.setenv(rbi.GIT_TIMEOUT_ENV, "0.75")
    _ = rbi.resolve_git_head_sha(repo)
    monkeypatch.setenv(rbi.GIT_TIMEOUT_ENV, "bad")
    _ = rbi.resolve_git_head_sha(repo)
    assert fake.timeouts == [0.75, rbi.DEFAULT_GIT_TIMEOUT_S]


def test_core_package_dir_is_the_real_path_of_this_package() -> None:
    assert rbi._core_package_dir() == Path(rbi.__file__).resolve().parent


def test_runtime_build_info_uses_chain_and_explicit_sha_skips_it(clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _install(monkeypatch, tmp_path, {tmp_path / "core_real": _SHA_B})
    assert rbi.RuntimeBuildInfo(tmp_path / "repo").git_head_sha == _SHA_B
    before = len(fake.calls)
    info = rbi.RuntimeBuildInfo(tmp_path / "repo", git_head_sha="forced")
    assert info.git_head_sha == "forced" and len(fake.calls) == before


def test_snapshot_fields_and_extra(clean_env: None) -> None:
    info = rbi.RuntimeBuildInfo(".", git_head_sha=_SHA_A)
    snap = info.snapshot({"x": 1})
    assert (snap["git_head_sha"], snap["x"]) == (_SHA_A, 1)
    assert isinstance(snap["boot_ts"], float)

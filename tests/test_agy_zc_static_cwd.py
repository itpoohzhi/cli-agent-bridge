from __future__ import annotations

import json
import logging
import os
import stat
import sys
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = REPO_ROOT / "bridges" / "agy-bridge"
for _path_entry in (str(REPO_ROOT), str(BRIDGE_DIR)):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)

from agy_runtime import zc_static_cwd  # noqa: E402

IS_ROOT = hasattr(os, "geteuid") and (os.geteuid() == 0 or os.getuid() == 0)
requires_non_root = pytest.mark.skipif(
    IS_ROOT, reason="static 0o555 semantics require a non-root uid"
)


class _StubMgr:
    """Unit-test stand-in for AgyZeroCanonProfileManager (contract subset)."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.real_home = base / "real-home"
        self.gemini_dir = base / ".gemini"
        self._zc_cwd = base / "agy-zc-cwd"

    @property
    def zc_cwd(self) -> Path:
        return self._zc_cwd

    def ensure_zc_cwd(self) -> Path:
        self._zc_cwd.mkdir(mode=0o700, parents=True, exist_ok=True)
        return self._zc_cwd

    def create_turn_zc_cwd(self) -> Path:
        self.ensure_zc_cwd()
        turn = self._zc_cwd / f"turn-{uuid.uuid4().hex[:12]}"
        turn.mkdir(mode=0o700)
        return turn

    def rotate_agy_runtime_artifacts(self) -> None:
        # Rotation may only prune agy-zc-cwd contents, never sibling dirs.
        if not self._zc_cwd.is_dir():
            return
        for stale in sorted(self._zc_cwd.glob("turn-*")):
            if stale.is_dir():
                os.chmod(stale, 0o700)

    def _reject_overlap(self, target: Path, label: str) -> None:
        for protected in (self.real_home, self.gemini_dir):
            if target == protected:
                raise RuntimeError(f"zc_overlap:{label}:protected")
            if protected in target.parents or target in protected.parents:
                raise RuntimeError(f"zc_overlap:{label}:nesting")


def _mgr(tmp_path: Path) -> _StubMgr:
    return _StubMgr(tmp_path / "zc")


def _static_dir(mgr: Any) -> Path:
    return mgr.zc_cwd.with_name(zc_static_cwd.DEFAULT_STATIC_DIR_NAME)


@pytest.fixture(autouse=True)
def _relax_tmp_path(tmp_path: Path) -> Iterator[None]:
    # RISK-006: pytest tmp_path teardown must never hit a 0o555 directory.
    yield
    for child in sorted(tmp_path.rglob("*"), reverse=True):
        if child.is_symlink():
            continue
        if child.is_dir():
            os.chmod(child, 0o700)


def _assert_fail_closed(mgr: Any, target: Path) -> None:
    with pytest.raises(RuntimeError):
        zc_static_cwd.ensure_static_cwd(target, mgr)


def _assert_degrades(
    mgr: Any,
    target: Path,
    caplog: pytest.LogCaptureFixture,
    env: dict[str, str] | None = None,
) -> None:
    with caplog.at_level(logging.WARNING):
        cwd = zc_static_cwd.acquire_turn_cwd(mgr, environ={} if env is None else env)
    assert cwd.ephemeral is True
    assert cwd.path != target
    assert cwd.path.is_dir()
    assert cwd.path.name.startswith("turn-")
    assert cwd.path.parent == mgr.zc_cwd
    assert "agy_zc_static_cwd_degraded" in caplog.text
    cwd.release()
    assert not cwd.path.exists()


@requires_non_root
def test_default_static_path_reused_across_turns(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    expected = _static_dir(mgr)
    first = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    second = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert first.ephemeral is False
    assert second.ephemeral is False
    assert first.path == expected
    assert second.path == expected
    assert expected.is_dir()
    assert stat.S_IMODE(expected.stat().st_mode) == 0o555
    assert list(expected.iterdir()) == []


@requires_non_root
def test_env_override_honors_sticky_parent(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    sticky = tmp_path / "sticky-parent"
    sticky.mkdir(mode=0o700)
    os.chmod(sticky, 0o1777)
    target = sticky / "agy-zc-static-cwd"
    env = {zc_static_cwd.STATIC_CWD_PATH_ENV: str(target)}
    turn = zc_static_cwd.acquire_turn_cwd(mgr, environ=env)
    assert turn.ephemeral is False
    assert turn.path == target
    assert stat.S_IMODE(target.stat().st_mode) == 0o555
    assert list(target.iterdir()) == []


@requires_non_root
def test_static_cwd_is_not_writable(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    turn = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    with pytest.raises(PermissionError):
        (turn.path / "evil.txt").write_text("pwned", encoding="utf-8")


@requires_non_root
def test_leaf_symlink_fail_closed_valid_and_dangling(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    base = mgr.base
    base.mkdir(mode=0o700, parents=True)
    real = base / "real-target"
    real.mkdir(mode=0o700)
    valid = base / "link-valid"
    valid.symlink_to(real)
    dangling = base / "link-dangling"
    dangling.symlink_to(base / "missing")
    for link in (valid, dangling):
        _assert_fail_closed(mgr, link)


@requires_non_root
def test_parent_symlink_fail_closed(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    base = mgr.base
    base.mkdir(mode=0o700, parents=True)
    real_parent = base / "real-parent"
    real_parent.mkdir(mode=0o700)
    linked = base / "link-parent"
    linked.symlink_to(real_parent)
    _assert_fail_closed(mgr, linked / "agy-zc-static-cwd")


@requires_non_root
def test_ancestor_symlink_fail_closed_before_mkdir(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    real = tmp_path / "real-tree"
    real.mkdir(mode=0o700)
    linked = tmp_path / "linked-tree"
    linked.symlink_to(real)
    target = linked / "nested" / "agy-zc-static-cwd"
    _assert_fail_closed(mgr, target)
    assert not (real / "nested").exists()


@requires_non_root
def test_relative_path_fail_closed(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    _assert_fail_closed(mgr, Path("relative/agy-zc-static-cwd"))


@requires_non_root
def test_parent_world_writable_without_sticky_fail_closed(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    loose = tmp_path / "loose-parent"
    loose.mkdir(mode=0o700)
    os.chmod(loose, 0o777)
    _assert_fail_closed(mgr, loose / "agy-zc-static-cwd")


@requires_non_root
def test_wrong_mode_0o755_fail_closed(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    static = _static_dir(mgr)
    static.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    static.mkdir(mode=0o755)
    _assert_fail_closed(mgr, static)


@requires_non_root
def test_wrong_mode_0o700_persistent_after_retries(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    static = _static_dir(mgr)
    static.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    static.mkdir(mode=0o700)
    _assert_fail_closed(mgr, static)


@requires_non_root
def test_non_empty_0o555_fail_closed(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    static = _static_dir(mgr)
    static.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    static.mkdir(mode=0o700)
    (static / "planted.txt").write_text("pwned", encoding="utf-8")
    os.chmod(static, 0o555)
    _assert_fail_closed(mgr, static)


@requires_non_root
def test_same_uid_plant_caught_on_next_turn(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    mgr = _mgr(tmp_path)
    first = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert first.ephemeral is False
    # ARCH_PANEL F-002: same-uid adversary relaxes the mode, plants a file,
    # then restores 0o555; strict verification fails closed (no fallback to
    # the tampered static dir) and acquire degrades to an ephemeral CWD.
    os.chmod(first.path, 0o700)
    (first.path / "planted.txt").write_text("pwned", encoding="utf-8")
    os.chmod(first.path, 0o555)
    _assert_fail_closed(mgr, first.path)
    _assert_degrades(mgr, first.path, caplog)


@requires_non_root
def test_overlap_with_protected_dirs_fail_closed(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    mgr.real_home.mkdir(mode=0o700, parents=True)
    mgr.gemini_dir.mkdir(mode=0o700, parents=True)
    for target in (
        mgr.real_home / "agy-zc-static-cwd",
        mgr.gemini_dir / "nested" / "agy-zc-static-cwd",
        mgr.base,
    ):
        _assert_fail_closed(mgr, target)


@requires_non_root
def test_uid_mismatch_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr = _mgr(tmp_path)
    sticky = tmp_path / "sticky"
    sticky.mkdir(mode=0o700)
    os.chmod(sticky, 0o1777)
    static = sticky / "agy-zc-static-cwd"
    static.mkdir(mode=0o555)
    fake_uid = os.getuid() + 4242
    monkeypatch.setattr(os, "getuid", lambda: fake_uid)
    monkeypatch.setattr(os, "geteuid", lambda: fake_uid)
    _assert_fail_closed(mgr, static)


@requires_non_root
@pytest.mark.parametrize(
    "kind",
    ("non_empty_0o555", "leaf_symlink", "wrong_mode_0o755", "overlap", "relative"),
)
def test_f002_acquire_degrades_safely_on_tampering(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    mgr = _mgr(tmp_path)
    env: dict[str, str] = {}
    if kind == "non_empty_0o555":
        target = _static_dir(mgr)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.mkdir(mode=0o700)
        (target / "planted.txt").write_text("pwned", encoding="utf-8")
        os.chmod(target, 0o555)
    elif kind == "leaf_symlink":
        real = tmp_path / "real-target"
        real.mkdir(mode=0o700)
        target = tmp_path / "link-target"
        target.symlink_to(real)
        env[zc_static_cwd.STATIC_CWD_PATH_ENV] = str(target)
    elif kind == "wrong_mode_0o755":
        target = _static_dir(mgr)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.mkdir(mode=0o755)
    elif kind == "overlap":
        mgr.real_home.mkdir(mode=0o700, parents=True)
        target = mgr.real_home / "agy-zc-static-cwd"
        env[zc_static_cwd.STATIC_CWD_PATH_ENV] = str(target)
    else:
        target = Path("relative/agy-zc-static-cwd")
        env[zc_static_cwd.STATIC_CWD_PATH_ENV] = str(target)
    _assert_degrades(mgr, target, caplog, env)


@requires_non_root
def test_f002_fail_closed_env_re_raises(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    static = _static_dir(mgr)
    static.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    static.mkdir(mode=0o755)
    env = {zc_static_cwd.STATIC_CWD_FAIL_CLOSED_ENV: "1"}
    with pytest.raises(RuntimeError):
        zc_static_cwd.acquire_turn_cwd(mgr, environ=env)


@requires_non_root
def test_f002_single_tamper_is_not_a_persistent_dos(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    first = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert first.ephemeral is False
    static = first.path
    os.chmod(static, 0o700)
    (static / "planted.txt").write_text("pwned", encoding="utf-8")
    os.chmod(static, 0o555)
    degraded = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert degraded.ephemeral is True
    assert degraded.path != static
    degraded.release()
    assert not degraded.path.exists()
    os.chmod(static, 0o700)
    (static / "planted.txt").unlink()
    os.chmod(static, 0o555)
    recovered = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert recovered.ephemeral is False
    assert recovered.path == static
    assert list(static.iterdir()) == []


def test_kill_switch_env_returns_ephemeral(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    env = {zc_static_cwd.STATIC_CWD_ENABLED_ENV: "0"}
    turn = zc_static_cwd.acquire_turn_cwd(mgr, environ=env)
    assert turn.ephemeral is True
    assert turn.path.parent == mgr.zc_cwd
    assert turn.path.name.startswith("turn-")
    assert turn.path.is_dir()
    turn.release()
    assert not turn.path.exists()
    assert list(mgr.zc_cwd.glob("turn-*")) == []


@requires_non_root
def test_dynamic_config_kill_switch_hot_reload(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    static = zc_static_cwd.acquire_turn_cwd(mgr, cfg, environ={})
    assert static.ephemeral is False
    cfg.write_text(
        json.dumps({zc_static_cwd.STATIC_CWD_ENABLED_KEY: False}),
        encoding="utf-8",
    )
    off = zc_static_cwd.acquire_turn_cwd(mgr, cfg, environ={})
    assert off.ephemeral is True
    assert off.path.name.startswith("turn-")
    off.release()
    assert not off.path.exists()
    cfg.write_text(
        json.dumps({zc_static_cwd.STATIC_CWD_ENABLED_KEY: True}),
        encoding="utf-8",
    )
    back = zc_static_cwd.acquire_turn_cwd(mgr, cfg, environ={})
    assert back.ephemeral is False
    assert back.path == static.path
    assert stat.S_IMODE(back.path.stat().st_mode) == 0o555


def test_root_refusal_returns_ephemeral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr = _mgr(tmp_path)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "getuid", lambda: 0)
    turn = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert turn.ephemeral is True
    assert turn.path.parent == mgr.zc_cwd
    assert turn.path.name.startswith("turn-")
    assert turn.path.is_dir()


@requires_non_root
def test_release_static_is_strict_noop(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    turn = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    assert turn.ephemeral is False
    turn.release()
    turn.release()
    assert turn.path.is_dir()
    assert stat.S_IMODE(turn.path.stat().st_mode) == 0o555
    assert list(turn.path.iterdir()) == []


@requires_non_root
def test_ensure_and_rotation_leave_static_untouched(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    turn = zc_static_cwd.acquire_turn_cwd(mgr, environ={})
    static = turn.path
    mgr.ensure_zc_cwd()
    mgr.rotate_agy_runtime_artifacts()
    mgr.ensure_zc_cwd()
    assert static.is_dir()
    assert stat.S_IMODE(static.stat().st_mode) == 0o555
    assert list(static.iterdir()) == []


@requires_non_root
def test_parallel_acquire_cold_start(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    expected = _static_dir(mgr)

    def _acquire(_index: int) -> zc_static_cwd.ZeroCanonTurnCwd:
        return zc_static_cwd.acquire_turn_cwd(mgr, environ={})

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_acquire, range(8)))
    assert {turn.path for turn in results} == {expected}
    assert all(turn.ephemeral is False for turn in results)
    assert stat.S_IMODE(expected.stat().st_mode) == 0o555
    assert list(expected.iterdir()) == []


@requires_non_root
def test_enabled_config_variants(tmp_path: Path) -> None:
    cfg = tmp_path / "dynamic_config.json"
    variants = (
        ('{"bridge_agy_zc_static_cwd_enabled": false}', False),
        ('{"bridge_agy_zc_static_cwd_enabled": 0}', False),
        ('{"bridge_agy_zc_static_cwd_enabled": "OFF"}', False),
        ('{"bridge_agy_zc_static_cwd_enabled": true}', True),
        ('{"bridge_agy_zc_static_cwd_enabled": 1}', True),
        ('{"bridge_agy_zc_static_cwd_enabled": "on"}', True),
        ('{"bridge_agy_zc_static_cwd_enabled": null}', False),
        ('{"bridge_agy_zc_static_cwd_enabled": [1]}', False),
        ('{"bridge_agy_zc_static_cwd_enabled": {"x": 1}}', False),
        ("{not json at all", False),
        ("[]", False),
    )
    for raw, expected in variants:
        cfg.write_text(raw, encoding="utf-8")
        assert zc_static_cwd.is_agy_static_cwd_enabled(cfg, environ={}) is expected


@requires_non_root
def test_f001_corrupt_config_fails_closed_not_open(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    mgr = _mgr(tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{not json at all", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        enabled = zc_static_cwd.is_agy_static_cwd_enabled(cfg, environ={})
        turn = zc_static_cwd.acquire_turn_cwd(mgr, cfg, environ={})
    assert enabled is False
    assert "agy_zc_static_cwd_config_unreadable" in caplog.text
    assert turn.ephemeral is True
    assert turn.path.name.startswith("turn-")
    turn.release()
    assert not turn.path.exists()


@requires_non_root
def test_f001_non_dict_root_fails_closed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    mgr = _mgr(tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("[]", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        enabled = zc_static_cwd.is_agy_static_cwd_enabled(cfg, environ={})
        turn = zc_static_cwd.acquire_turn_cwd(mgr, cfg, environ={})
    assert enabled is False
    assert "agy_zc_static_cwd_config_invalid_root" in caplog.text
    assert turn.ephemeral is True
    turn.release()
    assert not turn.path.exists()


@requires_non_root
def test_f001_non_scalar_value_fails_closed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text('{"bridge_agy_zc_static_cwd_enabled": [1]}', encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert zc_static_cwd.is_agy_static_cwd_enabled(cfg, environ={}) is False
    assert "agy_zc_static_cwd_config_bad_value" in caplog.text


@requires_non_root
def test_f001_directory_as_config_fails_closed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.mkdir(mode=0o700)
    with caplog.at_level(logging.WARNING):
        enabled = zc_static_cwd.is_agy_static_cwd_enabled(cfg, environ={})
    assert enabled is False
    assert "agy_zc_static_cwd_config_unreadable" in caplog.text


@requires_non_root
def test_f001_missing_config_defaults_enabled(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    missing = tmp_path / "dynamic_config.json"
    assert zc_static_cwd.is_agy_static_cwd_enabled(missing, environ={}) is True
    assert zc_static_cwd.is_agy_static_cwd_enabled(None, environ={}) is True
    turn = zc_static_cwd.acquire_turn_cwd(mgr, missing, environ={})
    assert turn.ephemeral is False


@requires_non_root
def test_f001_valid_dict_without_key_defaults_enabled(tmp_path: Path) -> None:
    mgr = _mgr(tmp_path)
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    assert zc_static_cwd.is_agy_static_cwd_enabled(cfg, environ={}) is True
    turn = zc_static_cwd.acquire_turn_cwd(mgr, cfg, environ={})
    assert turn.ephemeral is False

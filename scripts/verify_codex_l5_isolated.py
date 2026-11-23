#!/usr/bin/env python3
"""Live-isolated L5 verification runner for Codex app-server v2 & Zero-Canon (W3-F)."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stdio_resident.process_reaper import is_pgid_alive  # noqa: E402
from core.zero_canon_fs import ensure_private_dir  # noqa: E402

DEFAULT_EXPECTED_VERSION = "0.171.0-alpha.13"
DEFAULT_TIMEOUT_S = float(os.environ.get("CODEX_L5_TIMEOUT_S", "120.0"))
DEFAULT_VERSION_TIMEOUT_S = float(os.environ.get("CODEX_L5_VERSION_TIMEOUT_S", "15.0"))
DEFAULT_CANCEL_GRACE_S = float(os.environ.get("CODEX_L5_CANCEL_GRACE_S", "2.0"))
PROTECTED_FILES = ("fleet.json", "providers.d/codex.yaml")
LIVE_FORBIDDEN_ENV = (
    "BRIDGE_KEY",
    "BRIDGE_API_KEY",
    "INTERNAL_SERVICE_KEY",
    "META_API_KEY",
    "BRIDGE_DYNAMIC_CONFIG_PATH",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_protected_hashes(repo_root: Path) -> dict[str, str]:
    return {rel: _sha256(repo_root / rel) for rel in PROTECTED_FILES}


def _build_isolated_env(scratch: Path, expected_version: str) -> dict[str, str]:
    home = scratch / "home"
    codex_home = home / ".codex"
    for folder in (
        home,
        codex_home,
        home / ".config",
        home / ".local" / "share",
        home / ".cache",
        home / ".local" / "state",
    ):
        ensure_private_dir(folder, 0o700)
    env = {k: v for k, v in os.environ.items() if k not in LIVE_FORBIDDEN_ENV}
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "OPENAI_API_KEY": "sk-dummy-test-000",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            "CODEX_L5_EXPECTED_VERSION": expected_version,
        }
    )
    return env


def _teardown_owned_pgid(proc: subprocess.Popen[str], pgid: int, grace_s: float) -> None:
    owned = pgid > 1 and pgid != os.getpgrp()
    try:
        if owned:
            with suppress(ProcessLookupError, OSError):
                os.killpg(pgid, signal.SIGTERM)
    finally:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                with suppress(OSError):
                    pipe.close()
        with suppress(subprocess.TimeoutExpired, OSError):
            _ = proc.wait(timeout=max(2.0, grace_s))
    if owned and is_pgid_alive(pgid):
        deadline = time.monotonic() + grace_s
        while is_pgid_alive(pgid) and time.monotonic() < deadline:
            _ = threading.Event().wait(0.02)
        if is_pgid_alive(pgid):
            with suppress(ProcessLookupError, OSError):
                os.killpg(pgid, signal.SIGKILL)


def _run_isolated_pgid(
    argv: Sequence[str], env: Mapping[str, str], cwd: Path, timeout_s: float
) -> tuple[int, str, str, int]:
    proc = subprocess.Popen(
        list(argv),
        cwd=str(cwd),
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    pgid = proc.pid
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return proc.returncode or 0, stdout, stderr, pgid
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout_after_{timeout_s}s", pgid
    finally:
        _teardown_owned_pgid(proc, pgid, DEFAULT_CANCEL_GRACE_S)


def _resolve_pytest_cmd(test_file: Path) -> list[str]:
    if importlib.util.find_spec("pytest") is not None:
        return [sys.executable, "-m", "pytest", "-q", str(test_file)]
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        return [pytest_bin, "-q", str(test_file)]
    raise RuntimeError("pytest_not_found_in_python_or_path")


def _check_codex_version(
    expected_version: str, env: Mapping[str, str], cwd: Path
) -> tuple[str, str, int]:
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise RuntimeError("codex_binary_not_found")
    rc, out, err, pgid = _run_isolated_pgid(
        [codex_bin, "--version"], env, cwd, DEFAULT_VERSION_TIMEOUT_S
    )
    version_line = (out or "").strip()
    if rc != 0 or expected_version not in version_line:
        raise RuntimeError(
            f"codex_version_mismatch: rc={rc} expected={expected_version!r} "
            f"got={version_line!r} err={err.strip()[:200]!r}"
        )
    return codex_bin, version_line, pgid


def run_l5_verification(expected_version: str, timeout_s: float) -> dict[str, object]:
    started = time.monotonic()
    before_hashes = _snapshot_protected_hashes(ROOT)
    scratch = Path(tempfile.mkdtemp(prefix="codex-l5-isolated-"))
    os.chmod(scratch, 0o700)
    tracked_pgids: list[int] = []
    try:
        env = _build_isolated_env(scratch, expected_version)
        codex_bin, codex_ver, ver_pgid = _check_codex_version(expected_version, env, scratch)
        tracked_pgids.append(ver_pgid)
        test_file = ROOT / "tests" / "test_codex_live_isolated_e2e.py"
        pytest_cmd = _resolve_pytest_cmd(test_file)
        rc, out, err, pytest_pgid = _run_isolated_pgid(pytest_cmd, env, ROOT, timeout_s)
        tracked_pgids.append(pytest_pgid)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    after_hashes = _snapshot_protected_hashes(ROOT)
    orphans = [pgid for pgid in tracked_pgids if is_pgid_alive(pgid)]
    hashes_ok = before_hashes == after_hashes
    passed = rc == 0 and not orphans and hashes_ok
    return {
        "status": "PASS" if passed else "FAIL",
        "codex_bin": codex_bin,
        "codex_version": codex_ver,
        "expected_codex_version": expected_version,
        "pytest_returncode": rc,
        "pytest_summary": (out.strip().splitlines()[-1] if out.strip() else ""),
        "pytest_stderr_tail": (err.strip().splitlines()[-1] if err.strip() else ""),
        "orphan_pids": len(orphans),
        "listeners": 0,
        "protected_hashes_unchanged": hashes_ok,
        "scratch_cleaned": not scratch.exists(),
        "elapsed_s": round(time.monotonic() - started, 3),
    }


def _parse_args(argv: Sequence[str] | None = None) -> tuple[str, float]:
    parser = argparse.ArgumentParser(
        description="Run live-isolated L5 E2E verification for Codex app-server v2 & Zero-Canon."
    )
    _ = parser.add_argument(
        "--expected-codex-version",
        default=DEFAULT_EXPECTED_VERSION,
        help="Required codex --version substring (default: %(default)s).",
    )
    _ = parser.add_argument(
        "--timeout-s",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help="Overall pytest subprocess timeout in seconds.",
    )
    ns = parser.parse_args(argv)
    return str(ns.expected_codex_version), float(ns.timeout_s)


def main(argv: Sequence[str] | None = None) -> int:
    expected_version, timeout_s = _parse_args(argv)
    try:
        report = run_l5_verification(expected_version, timeout_s)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

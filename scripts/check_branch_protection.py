#!/usr/bin/env python3
"""Read-only verifier for GitHub branch protection and required CI status checks."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Protocol, cast

DEFAULT_REPO = "itpoohzhi/cli-agent-bridge"
DEFAULT_BRANCHES: tuple[str, ...] = ("dev", "main")
DEFAULT_REQUIRED_CHECKS: tuple[str, ...] = ("lint-types-test", "drain-macos")
DEFAULT_TIMEOUT_S = 15.0

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REMOTE_SLUG_RE = re.compile(r"[:/]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(https?://[^/\s:@]+:)[^@\s/]+(@)", re.IGNORECASE),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
)


@dataclass(frozen=True)
class BranchCheckResult:
    """Audit result for a single GitHub branch."""

    branch: str
    protected: bool
    configured_checks: list[str]
    missing_checks: list[str]
    gaps: list[str]


class _CliArgs(Protocol):
    """Typed view of parsed CLI arguments."""

    repo: str | None
    branches: list[str]
    required_checks: list[str]
    json: bool


def _redact(text: str) -> str:
    """Mask tokens and embedded URL credentials in diagnostic output."""
    masked = text.strip()
    for idx, pattern in enumerate(_SECRET_PATTERNS):
        repl = r"\1***\2" if idx == 0 else "***"
        masked = pattern.sub(repl, masked)
    return masked


def _read_timeout_s() -> float:
    """Read subprocess timeout from environment with safe fallback."""
    raw = os.environ.get("GH_API_TIMEOUT_S", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else DEFAULT_TIMEOUT_S


def _detect_repo() -> str:
    """Infer owner/repo from git origin remote, falling back to DEFAULT_REPO."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=_read_timeout_s(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return DEFAULT_REPO
    if proc.returncode != 0:
        return DEFAULT_REPO
    match = _REMOTE_SLUG_RE.search(proc.stdout.strip())
    if match and _REPO_RE.match(match.group(1)):
        return match.group(1)
    return DEFAULT_REPO


def _gh_api_get(endpoint: str, timeout_s: float) -> tuple[bool, object, str]:
    """Execute a strictly read-only GET call via gh api."""
    try:
        proc = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError:
        return False, None, "gh CLI not found in PATH"
    except subprocess.TimeoutExpired:
        return False, None, f"gh api timed out after {timeout_s:.1f}s"
    except OSError as exc:
        return False, None, _redact(str(exc))
    if proc.returncode != 0:
        return False, None, _redact(proc.stderr or proc.stdout or f"exit {proc.returncode}")
    try:
        return True, cast(object, json.loads(proc.stdout)), ""
    except json.JSONDecodeError as exc:
        return False, None, f"invalid JSON from gh api: {exc.msg}"


def _as_dict(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _as_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _collect_context_items(items: object, target: set[str]) -> None:
    """Add check context names from a list of dicts containing a 'context' key."""
    for entry in _as_list(items):
        entry_dict = _as_dict(entry)
        if entry_dict is None:
            continue
        ctx = entry_dict.get("context")
        if isinstance(ctx, str) and ctx:
            target.add(ctx)


def _extract_protection_checks(payload: object) -> set[str]:
    """Extract required check names from classic branch protection payload."""
    checks: set[str] = set()
    root = _as_dict(payload)
    rsc = _as_dict(root.get("required_status_checks")) if root is not None else None
    if rsc is None:
        return checks
    for ctx in _as_list(rsc.get("contexts")):
        if isinstance(ctx, str) and ctx:
            checks.add(ctx)
    _collect_context_items(rsc.get("checks"), checks)
    return checks


def _extract_ruleset_checks(payload: object) -> tuple[bool, set[str]]:
    """Extract required check names from branch rulesets payload."""
    checks: set[str] = set()
    has_rule = False
    for rule in _as_list(payload):
        rule_dict = _as_dict(rule)
        if rule_dict is None or rule_dict.get("type") != "required_status_checks":
            continue
        has_rule = True
        params = _as_dict(rule_dict.get("parameters"))
        if params is not None:
            _collect_context_items(params.get("required_status_checks"), checks)
    return has_rule, checks


def _check_branch(
    repo: str,
    branch: str,
    required_checks: Sequence[str],
    timeout_s: float,
) -> BranchCheckResult:
    """Audit classic branch protection and rulesets for one branch."""
    encoded = urllib.parse.quote(branch, safe="")
    ok_prot, prot_data, prot_err = _gh_api_get(f"repos/{repo}/branches/{encoded}/protection", timeout_s)
    ok_rules, rules_data, rules_err = _gh_api_get(f"repos/{repo}/rules/branches/{encoded}", timeout_s)

    configured: set[str] = _extract_protection_checks(prot_data) if ok_prot else set()
    has_ruleset, ruleset_checks = (
        _extract_ruleset_checks(rules_data) if ok_rules else (False, set[str]())
    )
    configured.update(ruleset_checks)
    protected = ok_prot or has_ruleset

    gaps: list[str] = []
    if not protected:
        gaps.append(f"classic protection unavailable: {prot_err}")
    if not ok_rules and not ok_prot:
        gaps.append(f"rulesets unavailable: {rules_err}")
    missing = [chk for chk in required_checks if chk not in configured]
    if missing:
        gaps.append(f"missing required checks: {', '.join(missing)}")

    return BranchCheckResult(branch, protected, sorted(configured), missing, gaps)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Read-only check for GitHub branch protection and required CI checks."
    )
    _ = parser.add_argument("--repo", default=None, help="GitHub owner/name (default: origin).")
    _ = parser.add_argument("--branches", nargs="+", default=list(DEFAULT_BRANCHES), help="Branches.")
    _ = parser.add_argument(
        "--required-checks", nargs="+", default=list(DEFAULT_REQUIRED_CHECKS), help="Required checks."
    )
    _ = parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    return parser


def _print_text_report(repo: str, results: Sequence[BranchCheckResult]) -> None:
    """Print human-readable branch protection audit report."""
    print(f"Branch protection audit for {repo}:")
    for res in results:
        status = "OK" if not res.gaps else "FAIL"
        checks_str = ", ".join(res.configured_checks) or "(none)"
        print(f"  [{status}] {res.branch}: protected={res.protected}, checks=[{checks_str}]")
        for gap in res.gaps:
            print(f"         gap: {gap}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint; returns 0 when all branches pass, 1 on any gap or invalid input."""
    args = cast(_CliArgs, cast(object, _build_parser().parse_args(argv)))
    repo = args.repo or _detect_repo()
    if not _REPO_RE.match(repo):
        print(f"Invalid --repo format '{_redact(repo)}'; expected owner/name.", file=sys.stderr)
        return 1

    timeout_s = _read_timeout_s()
    results = [_check_branch(repo, b, args.required_checks, timeout_s) for b in args.branches]
    all_ok = all(not res.gaps for res in results)
    if args.json:
        print(json.dumps({"repo": repo, "ok": all_ok, "branches": [asdict(r) for r in results]}, indent=2))
    else:
        _print_text_report(repo, results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

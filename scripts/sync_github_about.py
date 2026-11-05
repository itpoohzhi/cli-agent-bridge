#!/usr/bin/env python3
"""Synchronise GitHub repository "About" metadata (description, homepage, topics).

The module is standard-library only and exposes a small, auditable surface for
validating, checking and applying the metadata stored in
``.github/repo-metadata.json``. All failures are reported with redacted text so
that tokens can never leak into logs or CI output.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Any

DEFAULT_METADATA_PATH = Path(__file__).resolve().parents[1] / ".github" / "repo-metadata.json"
DEFAULT_REPO = "itpoohzhi/cli-agent-bridge"
DEFAULT_API_URL = "https://api.github.com"

# Protocol constants. These are fixed by the GitHub "About" contract and are
# deliberately NOT overridable through environment variables.
MAX_DESCRIPTION_LEN = 240
MIN_TOPICS_COUNT = 1
MAX_TOPICS_COUNT = 20
EXPECTED_TOPICS_COUNT = MAX_TOPICS_COUNT
MAX_TOPIC_LEN = 50
MAX_HOMEPAGE_LEN = 256

DEFAULT_ALLOWED_API_HOSTS: frozenset[str] = frozenset({"api.github.com"})
ALLOWED_API_HOSTS = DEFAULT_ALLOWED_API_HOSTS

_TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOPIC_RE = _TOPIC_RE
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

MASK = "***MASKED***"
_USERINFO_MASK = "***REDACTED***"

_TOKEN_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")
_SAFE_TIMEOUT_ENV = "GITHUB_HTTP_TIMEOUT_S"
_DEFAULT_TIMEOUT_S = 15.0
_USER_AGENT = "sync-github-about/1.0"
_AUTH_FALLBACK_WARNING = (
    "Provided GITHUB_TOKEN was rejected (HTTP 401); fell back to "
    "unauthenticated public read."
)

_SECRET_PATTERNS = (
    re.compile(r"(https?://[^/\s:@]+:)[^@\s/]+(@)", re.IGNORECASE),
    re.compile(r"(//[^/\s:@]+:)[^@\s/]+(@)"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
)

_HOSTNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?$")


class _GitHubHTTPError(RuntimeError):
    """HTTP error from the GitHub API that carries the numeric status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def mask_secret(text: str, secret: str | None = None) -> str:
    """Redact secrets, credentials and well-known token shapes from ``text``."""
    if text is None:
        return ""

    result = str(text)

    for pattern in _SECRET_PATTERNS[:2]:
        result = pattern.sub(rf"\1{_USERINFO_MASK}\2", result)

    candidates: list[str] = []
    if secret:
        candidates.append(secret)
    for name in _TOKEN_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            candidates.append(value)

    for value in candidates:
        if value and value in result:
            result = result.replace(value, MASK)

    for pattern in _SECRET_PATTERNS[2:]:
        result = pattern.sub(MASK, result)

    return result


def _normalise_allowed_hosts(
    allowed_hosts: AbstractSet[str] | None,
) -> frozenset[str]:
    """Normalise an explicit host allowlist without consulting the environment."""
    if allowed_hosts is None:
        return DEFAULT_ALLOWED_API_HOSTS

    return frozenset(
        host.strip().lower()
        for host in allowed_hosts
        if isinstance(host, str) and host.strip()
    )


def _allowed_api_hosts() -> frozenset[str]:
    """Return the built-in GitHub API hostname allowlist."""
    return DEFAULT_ALLOWED_API_HOSTS


def _effective_port(parsed: urllib.parse.SplitResult) -> int | None:
    """Return the effective port (``443`` by default) or ``None`` when invalid."""
    try:
        port = parsed.port
    except ValueError:
        return None
    return 443 if port is None else port


def validate_api_url(
    api_url: str,
    *,
    allowed_hosts: AbstractSet[str] | None = None,
) -> str:
    """Validate and normalise a trusted GitHub API base URL."""
    if not isinstance(api_url, str) or not api_url:
        raise ValueError("api_url must be a non-empty string")

    for char in api_url:
        if char.isspace() or ord(char) < 32 or ord(char) == 127:
            raise ValueError("api_url must not contain whitespace or control characters")

    try:
        parsed = urllib.parse.urlsplit(api_url)
    except (ValueError, UnicodeError):
        raise ValueError("api_url must include a valid hostname") from None

    try:
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
    except (ValueError, UnicodeError):
        raise ValueError("api_url must include a valid hostname") from None

    if username is not None or password is not None:
        raise ValueError("api_url must not contain embedded credentials")
    if parsed.scheme != "https":
        raise ValueError("api_url must use https scheme")
    if not hostname:
        raise ValueError("api_url must include a valid hostname")
    if parsed.query or parsed.fragment:
        raise ValueError("api_url must not include query or fragment parameters")

    try:
        port = parsed.port
    except ValueError:
        raise ValueError("api_url port must be 443 or omitted") from None
    if port not in (None, 443):
        raise ValueError("api_url port must be 443 or omitted")

    normalised_hostname = hostname.lower()
    if not _HOSTNAME_RE.fullmatch(normalised_hostname):
        raise ValueError("api_url must include a valid hostname")

    trusted_hosts = _normalise_allowed_hosts(allowed_hosts)
    if normalised_hostname not in trusted_hosts:
        raise ValueError(
            "api_url hostname is not in the trusted GitHub API host allowlist"
        )

    return api_url.rstrip("/")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that refuses unsafe or untrusted redirects."""

    def __init__(
        self,
        allowed_hosts: AbstractSet[str] | None = None,
    ) -> None:
        super().__init__()
        self.allowed_hosts = _normalise_allowed_hosts(allowed_hosts)

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Allow redirects only when scheme, hostname and port stay identical."""
        try:
            target = urllib.parse.urlsplit(newurl)
            original = urllib.parse.urlsplit(req.full_url)
            origin_host = (original.hostname or "").lower()
            target_host = (target.hostname or "").lower()
            target_port = _effective_port(target)
            origin_port = _effective_port(original)
            target_username = target.username
            target_password = target.password
        except (ValueError, UnicodeError):
            target = None
            original = None
            origin_host = ""
            target_host = ""
            target_port = None
            origin_port = None
            target_username = None
            target_password = None

        blocked = (
            target is None
            or original is None
            or target.scheme != "https"
            or target_host != origin_host
            or target_host not in self.allowed_hosts
            or origin_host not in self.allowed_hosts
            or target_username is not None
            or target_password is not None
            or target_port is None
            or origin_port is None
            or target_port != origin_port
        )
        if blocked:
            raise urllib.error.HTTPError(
                newurl,
                code,
                "Cross-host, credentialed or port-changing redirect blocked",
                headers,
                fp,
            )

        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener(
    allowed_hosts: AbstractSet[str] | None = None,
) -> urllib.request.OpenerDirector:
    """Build the default opener with the safe redirect handler installed."""
    return urllib.request.build_opener(_SafeRedirectHandler(allowed_hosts))


def _decode_json(
    raw_bytes: bytes,
    *,
    context: str,
    secret: str | None = None,
) -> Any:
    """Decode a JSON response without exposing malformed response content."""
    if not raw_bytes:
        return {}

    try:
        return json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError(
            mask_secret(
                f"{context}: invalid JSON response from GitHub API",
                secret=secret,
            )
        ) from None


def _request_json(
    opener: Any,
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: Any = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    allowed_hosts: AbstractSet[str] | None = None,
) -> Any:
    """Perform an HTTP request and return the decoded JSON payload."""
    url = validate_api_url(url, allowed_hosts=allowed_hosts)

    data: bytes | None = None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": _USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with opener.open(request, timeout=timeout_s) as response:
            raw_bytes = response.read()
            return _decode_json(
                raw_bytes,
                context=f"{method} {url}",
                secret=token,
            )
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            raw_err = exc.read().decode("utf-8", errors="replace")
            safe_body = mask_secret(raw_err, secret=token)
            body = safe_body[:500]
        except Exception:
            body = ""

        raise _GitHubHTTPError(
            exc.code,
            mask_secret(
                f"HTTP {exc.code} for {method} {url}: {body}",
                secret=token,
            ),
        ) from None
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        http.client.HTTPException,
    ) as exc:
        raise RuntimeError(
            mask_secret(
                f"GitHub API network error for {method} {url}: {exc}",
                secret=token,
            )
        ) from None


def load_metadata(path: Path = DEFAULT_METADATA_PATH) -> dict[str, Any]:
    """Load and parse the repository metadata JSON document."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read metadata file {path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Metadata file {path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Metadata file {path} must contain a JSON object")

    return data


def _has_control_chars(value: str) -> bool:
    """Return True when ``value`` contains C0 or DEL control characters."""
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def validate_metadata(
    metadata: dict[str, Any],
    *,
    min_topics: int = MIN_TOPICS_COUNT,
    max_topics: int = MAX_TOPICS_COUNT,
) -> list[str]:
    """Return a list of validation errors (``[]`` when metadata is valid)."""
    errors: list[str] = []

    if not isinstance(metadata, dict):
        return ["metadata: must be a JSON object"]

    description = metadata.get("description")
    if not isinstance(description, str) or not description:
        errors.append("description: must be a non-empty string")
    else:
        if description != description.strip():
            errors.append("description: must not have leading or trailing whitespace")
        if _has_control_chars(description):
            errors.append("description: must not contain control characters")
        if len(description) > MAX_DESCRIPTION_LEN:
            errors.append(
                f"description: must be at most {MAX_DESCRIPTION_LEN} characters "
                f"(got {len(description)})"
            )

    homepage = metadata.get("homepage")
    if not isinstance(homepage, str) or not homepage:
        errors.append("homepage: must be a non-empty string")
    else:
        if homepage != homepage.strip():
            errors.append("homepage: must not have leading or trailing whitespace")
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in homepage):
            errors.append("homepage: must not contain whitespace or control characters")
        if len(homepage) > MAX_HOMEPAGE_LEN:
            errors.append(
                f"homepage: must be at most {MAX_HOMEPAGE_LEN} characters "
                f"(got {len(homepage)})"
            )
        parsed = urllib.parse.urlsplit(homepage)
        if parsed.scheme != "https":
            errors.append("homepage: must use the https scheme")
        if not parsed.hostname:
            errors.append("homepage: must contain a hostname")
        if parsed.username is not None or parsed.password is not None:
            errors.append("homepage: must not contain credentials")
        try:
            parsed.port
        except ValueError:
            errors.append("homepage: invalid port")
        if parsed.hostname and not _HOSTNAME_RE.fullmatch(parsed.hostname.lower()):
            errors.append("homepage: must contain a valid hostname")

    topics = metadata.get("topics")
    if not isinstance(topics, list):
        errors.append("topics: must be a list of strings")
    else:
        if not (min_topics <= len(topics) <= max_topics):
            errors.append(
                f"topics: must contain between {min_topics} and {max_topics} "
                f"entries (got {len(topics)})"
            )
        seen: set[str] = set()
        for index, topic in enumerate(topics):
            if not isinstance(topic, str):
                errors.append(f"topics[{index}]: must be a string")
                continue
            if not (1 <= len(topic) <= MAX_TOPIC_LEN):
                errors.append(
                    f"topics[{index}]: length must be between 1 and {MAX_TOPIC_LEN} "
                    f"(got {len(topic)})"
                )
            if not _TOPIC_RE.fullmatch(topic):
                errors.append(
                    f"topics[{index}]: {topic!r} must match {_TOPIC_RE.pattern}"
                )
            if topic in seen:
                errors.append(f"topics[{index}]: duplicate topic {topic!r}")
            seen.add(topic)

    return errors


def compute_drift(
    desired: dict[str, Any],
    live: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return the differing fields between desired and live metadata."""
    drift: dict[str, dict[str, Any]] = {}

    for field in ("description", "homepage"):
        want = desired.get(field)
        have = live.get(field)
        if want != have:
            drift[field] = {"desired": want, "live": have}

    desired_topics = sorted(desired.get("topics") or [])
    live_topics = sorted(live.get("topics") or [])
    if desired_topics != live_topics:
        drift["topics"] = {"desired": desired_topics, "live": live_topics}

    return drift


def _extract_live_topics(topics_data: Any) -> list[str]:
    """Extract and strictly validate topic names from a GitHub API response."""
    error_message = (
        "Unexpected GitHub API response format for /topics: "
        "expected object with list[str] 'names'"
    )

    if not isinstance(topics_data, dict):
        raise RuntimeError(error_message)
    if "names" not in topics_data:
        raise RuntimeError(error_message)

    names = topics_data["names"]
    if not isinstance(names, list):
        raise RuntimeError(error_message)
    if any(
        not isinstance(item, str) or not _TOPIC_RE.fullmatch(item)
        for item in names
    ):
        raise RuntimeError(error_message)

    return list(names)


def fetch_live_metadata_with_auth_status(
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
    opener: Any = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    *,
    allow_unauth_fallback: bool = True,
    allowed_hosts: AbstractSet[str] | None = None,
    emit_auth_warning: bool = False,
) -> tuple[dict[str, Any], bool, str | None]:
    """Fetch live metadata and return its authentication status."""
    api_url = validate_api_url(api_url, allowed_hosts=allowed_hosts)
    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
        raise ValueError(f"repo must match {REPO_RE.pattern}: {repo!r}")

    trusted_hosts = _normalise_allowed_hosts(allowed_hosts)
    client = (
        opener
        if opener is not None
        else _build_opener(allowed_hosts=trusted_hosts)
    )

    authenticated = bool(token and token.strip())
    current_token = token if authenticated else None
    auth_warning: str | None = None

    repo_path = f"/repos/{repo}"
    try:
        repo_data = _request_json(
            client,
            api_url + repo_path,
            token=current_token,
            timeout_s=timeout_s,
            allowed_hosts=trusted_hosts,
        )
    except _GitHubHTTPError as exc:
        if (
            allow_unauth_fallback
            and current_token is not None
            and exc.status_code == 401
        ):
            current_token = None
            authenticated = False
            auth_warning = _AUTH_FALLBACK_WARNING
            if emit_auth_warning:
                sys.stderr.write(f"Warning: {auth_warning}\n")
            repo_data = _request_json(
                client,
                api_url + repo_path,
                token=None,
                timeout_s=timeout_s,
                allowed_hosts=trusted_hosts,
            )
        else:
            raise

    if not isinstance(repo_data, dict):
        raise RuntimeError("Unexpected GitHub response for /repos payload")

    topics_data = _request_json(
        client,
        f"{api_url}/repos/{repo}/topics",
        token=current_token,
        timeout_s=timeout_s,
        allowed_hosts=trusted_hosts,
    )
    topics = _extract_live_topics(topics_data)

    return (
        {
            "description": repo_data.get("description"),
            "homepage": repo_data.get("homepage"),
            "topics": topics,
        },
        authenticated,
        auth_warning,
    )


def fetch_live_metadata(
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
    opener: Any = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    *,
    allow_unauth_fallback: bool = True,
    allowed_hosts: AbstractSet[str] | None = None,
) -> dict[str, Any]:
    """Fetch the live "About" metadata for ``repo``."""
    live, _, _ = fetch_live_metadata_with_auth_status(
        repo=repo,
        token=token,
        api_url=api_url,
        opener=opener,
        timeout_s=timeout_s,
        allow_unauth_fallback=allow_unauth_fallback,
        allowed_hosts=allowed_hosts,
    )
    return live


def check_metadata(
    desired: dict[str, Any],
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
    opener: Any = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    *,
    allow_unauth_fallback: bool = True,
    strict_auth: bool = False,
    allowed_hosts: AbstractSet[str] | None = None,
) -> dict[str, Any]:
    """Compare desired metadata with the live repository metadata."""
    metadata_errors = validate_metadata(desired)
    if metadata_errors:
        raise ValueError("Invalid metadata: " + "; ".join(metadata_errors))

    live, authenticated, auth_warning = fetch_live_metadata_with_auth_status(
        repo=repo,
        token=token,
        api_url=api_url,
        opener=opener,
        timeout_s=timeout_s,
        allow_unauth_fallback=allow_unauth_fallback and not strict_auth,
        allowed_hosts=allowed_hosts,
        emit_auth_warning=True,
    )
    drift = compute_drift(desired, live)

    return {
        "in_sync": not drift,
        "repo": repo,
        "diff": drift,
        "live": live,
        "authenticated": authenticated,
        "auth_warning": auth_warning,
    }


def apply_metadata(
    desired: dict[str, Any],
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
    opener: Any = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    *,
    allowed_hosts: AbstractSet[str] | None = None,
) -> dict[str, Any]:
    """Apply ``desired`` metadata to ``repo`` and verify it by read-back."""
    if not token or not str(token).strip():
        raise ValueError("A GitHub token is required to apply metadata")

    metadata_errors = validate_metadata(desired)
    if metadata_errors:
        raise ValueError("Invalid metadata: " + "; ".join(metadata_errors))

    trusted_hosts = _normalise_allowed_hosts(allowed_hosts)
    api_url = validate_api_url(api_url, allowed_hosts=trusted_hosts)

    live = fetch_live_metadata(
        repo=repo,
        token=token,
        api_url=api_url,
        opener=opener,
        timeout_s=timeout_s,
        allow_unauth_fallback=False,
        allowed_hosts=trusted_hosts,
    )

    drift = compute_drift(desired, live)
    if not drift:
        return {"applied": False, "steps_completed": [], "diff": {}, "live": live}

    client = (
        opener
        if opener is not None
        else _build_opener(allowed_hosts=trusted_hosts)
    )
    steps_completed: list[str] = []

    if "description" in drift or "homepage" in drift:
        _request_json(
            client,
            f"{api_url}/repos/{repo}",
            method="PATCH",
            token=token,
            payload={
                "description": desired["description"],
                "homepage": desired["homepage"],
            },
            timeout_s=timeout_s,
            allowed_hosts=trusted_hosts,
        )
        steps_completed.append("patch_repo")

    if "topics" in drift:
        try:
            _request_json(
                client,
                f"{api_url}/repos/{repo}/topics",
                method="PUT",
                token=token,
                payload={"names": list(desired["topics"])},
                timeout_s=timeout_s,
                allowed_hosts=trusted_hosts,
            )
        except Exception as exc:
            raise RuntimeError(
                mask_secret(
                    f"{exc} (partial apply: steps_completed={steps_completed})",
                    secret=token,
                )
            ) from None
        steps_completed.append("put_topics")

    verified_live = fetch_live_metadata(
        repo=repo,
        token=token,
        api_url=api_url,
        opener=opener,
        timeout_s=timeout_s,
        allow_unauth_fallback=False,
        allowed_hosts=trusted_hosts,
    )

    post_drift = compute_drift(desired, verified_live)
    if post_drift:
        raise RuntimeError(
            mask_secret(
                f"Post-apply read-back drift detected: {post_drift} "
                f"(steps_completed={steps_completed})",
                secret=token,
            )
        )

    return {
        "applied": True,
        "steps_completed": steps_completed,
        "diff": drift,
        "live": verified_live,
    }


def _token_from_env() -> str | None:
    """Return the first non-empty GitHub token from the environment."""
    for name in _TOKEN_ENV_NAMES:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _safe_timeout_from_env(default: float = _DEFAULT_TIMEOUT_S) -> float:
    """Parse ``GITHUB_HTTP_TIMEOUT_S`` defensively; fall back to ``default``."""
    raw = os.environ.get(_SAFE_TIMEOUT_ENV)
    if raw is None:
        return default

    text = raw.strip()
    if not text:
        return default

    try:
        value = float(text)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(value) or value <= 0:
        return default

    return value


def _dump(value: Any, *, secret: str | None = None) -> str:
    """Serialise ``value`` as pretty JSON with secrets redacted."""
    return mask_secret(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True),
        secret=secret,
    )


def _report_error(message: str, *, secret: str | None = None) -> None:
    """Write a redacted error line to standard error."""
    print(mask_secret(f"error: {message}", secret=secret), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="sync_github_about.py",
        description="Validate, check and apply GitHub repository About metadata.",
    )
    parser.add_argument(
        "--metadata",
        default=str(DEFAULT_METADATA_PATH),
        help="Path to the metadata JSON file.",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="GitHub repository in owner/name form.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("GITHUB_API_URL", DEFAULT_API_URL),
        help="GitHub API base URL (validated only for --check/--apply).",
    )
    parser.add_argument(
        "--allow-custom-api-host",
        action="append",
        default=[],
        metavar="HOST",
        help="Explicitly trust an additional GitHub API hostname.",
    )
    parser.add_argument(
        "--strict-auth",
        action="store_true",
        help="Do not fall back to unauthenticated reads after an HTTP 401.",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validate", action="store_true", help="Validate metadata offline.")
    mode.add_argument("--dry-run", action="store_true", help="Show metadata offline (default).")
    mode.add_argument("--check", action="store_true", help="Compare metadata with the live repo.")
    mode.add_argument("--apply", action="store_true", help="Apply metadata to the live repo.")

    return parser


def main(argv: list[str] | None = None, *, opener: Any = None) -> int:
    """Run the command line interface; return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    token = _token_from_env()

    custom_hosts: set[str] = set()
    for raw_host in args.allow_custom_api_host:
        candidate = raw_host.strip().lower()
        if not candidate or not _HOSTNAME_RE.fullmatch(candidate):
            _report_error(
                "allow-custom-api-host must be a valid hostname",
                secret=token,
            )
            return 2
        custom_hosts.add(candidate)

    allowed_hosts = frozenset(DEFAULT_ALLOWED_API_HOSTS | custom_hosts)

    if not isinstance(args.repo, str) or not REPO_RE.fullmatch(args.repo):
        _report_error(
            f"repo must match {REPO_RE.pattern}: {args.repo!r}",
            secret=token,
        )
        return 2

    try:
        data = load_metadata(Path(args.metadata).expanduser())
    except ValueError as exc:
        _report_error(str(exc), secret=token)
        return 2

    errors = validate_metadata(data)

    if args.validate:
        if errors:
            print(_dump({"valid": False, "errors": errors}, secret=token))
            return 2
        print(_dump({"valid": True, "errors": [], "metadata": data}, secret=token))
        return 0

    if args.dry_run or (not args.check and not args.apply):
        if errors:
            print(_dump({"valid": False, "errors": errors}, secret=token))
            return 2
        print(
            _dump(
                {"valid": True, "errors": [], "dry_run": True, "metadata": data},
                secret=token,
            )
        )
        return 0

    if errors:
        print(_dump({"valid": False, "errors": errors}, secret=token))
        return 2

    timeout_s = _safe_timeout_from_env()

    if args.check:
        try:
            result = check_metadata(
                data,
                repo=args.repo,
                token=token,
                api_url=args.api_url,
                opener=opener,
                timeout_s=timeout_s,
                strict_auth=args.strict_auth,
                allowed_hosts=allowed_hosts,
            )
        except (ValueError, RuntimeError) as exc:
            _report_error(str(exc), secret=token)
            return 1

        print(_dump(result, secret=token))
        return 0 if result["in_sync"] else 1

    if args.apply:
        if token is None:
            _report_error(
                "GITHUB_TOKEN or GH_TOKEN is required for --apply",
                secret=token,
            )
            return 2

        try:
            result = apply_metadata(
                data,
                repo=args.repo,
                token=token,
                api_url=args.api_url,
                opener=opener,
                timeout_s=timeout_s,
                allowed_hosts=allowed_hosts,
            )
        except (ValueError, RuntimeError) as exc:
            _report_error(str(exc), secret=token)
            return 1

        print(_dump(result, secret=token))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())

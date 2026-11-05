"""Юнит-тесты синхронизации GitHub About (description/homepage/topics)."""

import http.client
import io
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sync_github_about import (
    DEFAULT_API_URL,
    DEFAULT_METADATA_PATH,
    DEFAULT_REPO,
    EXPECTED_TOPICS_COUNT,
    MAX_DESCRIPTION_LEN,
    _GitHubHTTPError,
    _SafeRedirectHandler,
    apply_metadata,
    check_metadata,
    compute_drift,
    fetch_live_metadata,
    load_metadata,
    main,
    mask_secret,
    validate_api_url,
    validate_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    """Минимальный ответ, совместимый с `with opener.open(...) as resp`."""

    def __init__(self, payload):
        if isinstance(payload, bytes):
            self._payload = payload
        else:
            self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _ScriptedOpener:
    """Опенер, отдающий заранее заданные ответы либо поднимающий исключения."""

    def __init__(self, handler):
        self._handler = handler
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append(request)
        return self._handler(request, timeout)


class _StatefulOpener:
    """Опенер с состоянием репозитория: PATCH/PUT меняют state, GET его читает."""

    def __init__(self, initial, fail_put=False):
        self.state = json.loads(json.dumps(initial))
        self.requests = []
        self.fail_put = fail_put

    def open(self, request, timeout=None):
        self.requests.append(request)
        method = request.get_method()

        if method == "PATCH":
            payload = json.loads(request.data.decode("utf-8"))
            self.state.update(payload)
            return _FakeResponse(self.state)

        if method == "PUT":
            if self.fail_put:
                raise urllib.error.HTTPError(
                    request.full_url,
                    500,
                    "Internal Server Error",
                    Message(),
                    None,
                )
            payload = json.loads(request.data.decode("utf-8"))
            self.state["topics"] = list(payload["names"])
            return _FakeResponse({"names": list(payload["names"])})

        if method == "GET":
            if request.full_url.endswith("/topics"):
                return _FakeResponse({"names": list(self.state.get("topics", []))})
            return _FakeResponse(
                {
                    "description": self.state.get("description", ""),
                    "homepage": self.state.get("homepage", ""),
                }
            )

        raise AssertionError(f"unexpected method: {method}")


@pytest.fixture
def metadata():
    return {
        "description": "Automated sync of the repository about section.",
        "homepage": "https://example.com",
        "topics": sorted(
            f"topic-{index:02d}" for index in range(EXPECTED_TOPICS_COUNT)
        ),
    }


def test_repo_metadata_ssot_valid():
    data = load_metadata(DEFAULT_METADATA_PATH)

    assert validate_metadata(data) == []
    assert len(data["description"]) <= MAX_DESCRIPTION_LEN
    assert len(data["topics"]) == EXPECTED_TOPICS_COUNT == 20
    assert data["topics"] == sorted(data["topics"])


def test_validate_metadata_rejects_invalid_inputs():
    valid = load_metadata(DEFAULT_METADATA_PATH)

    def errors_for(**overrides):
        payload = dict(valid)
        payload.update(overrides)
        return validate_metadata(payload)

    assert errors_for(description="x" * (MAX_DESCRIPTION_LEN + 1))
    assert errors_for(description=" leading space")
    assert errors_for(description="trailing space ")
    assert errors_for(description="bad\x00char")
    assert errors_for(homepage="https://")
    assert errors_for(homepage="http://example.com")
    assert errors_for(homepage="https://user:pass@example.com")
    assert errors_for(homepage="https://exa mple.com")
    assert errors_for(topics=valid["topics"][:-1] + ["abc-"])
    assert errors_for(topics=valid["topics"][:-1] + [valid["topics"][0]])
    assert errors_for(topics=[])
    assert errors_for(topics=valid["topics"] + ["overflow-topic"])


def test_validate_metadata_allows_1_to_20_topics():
    payload = {
        "description": "Valid repository metadata.",
        "homepage": "https://example.com",
        "topics": ["alpha", "beta", "delta", "epsilon", "gamma"],
    }

    assert validate_metadata(payload) == []

    one_topic = dict(payload, topics=["alpha"])
    assert validate_metadata(one_topic) == []

    no_topics = dict(payload, topics=[])
    assert validate_metadata(no_topics)

    too_many_topics = dict(
        payload,
        topics=[f"topic-{index:02d}" for index in range(21)],
    )
    assert validate_metadata(too_many_topics)

    meta = json.loads(
        (REPO_ROOT / ".github" / "repo-metadata.json").read_text(encoding="utf-8")
    )
    assert len(meta["topics"]) == 20


def test_validate_api_url_and_redirect_security():
    bad_urls = [
        "http://api.github.com",
        "https://evil.example.com",
        "https://user:pass@api.github.com",
        " https://api.github.com",
        "https://api.github.com ",
    ]
    for url in bad_urls:
        with pytest.raises((ValueError, RuntimeError)):
            validate_api_url(url)

    validate_api_url(DEFAULT_API_URL)

    handler = _SafeRedirectHandler()
    request = urllib.request.Request(
        f"{DEFAULT_API_URL}/repos/{DEFAULT_REPO}", method="GET"
    )

    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            Message(),
            "https://evil.example.com/repos",
        )

    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            Message(),
            "http://api.github.com/repos",
        )

    redirected = handler.redirect_request(
        request,
        None,
        301,
        "Moved",
        Message(),
        f"{DEFAULT_API_URL}/repos/moved",
    )
    assert redirected is not None


def test_url_credentials_never_leak_in_validation_or_stderr(capsys):
    api_url = "https://alice:s3cr3tPass@api.github.com "

    with pytest.raises((ValueError, RuntimeError)) as excinfo:
        validate_api_url(api_url)

    validation_message = str(excinfo.value)
    assert "s3cr3tPass" not in validation_message
    assert "alice" not in validation_message

    exit_code = main(["--check", "--api-url", api_url])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "s3cr3tPass" not in captured.err
    assert "alice" not in captured.err


def test_host_trust_boundary_ignores_env_and_requires_cli_opt_in(monkeypatch):
    monkeypatch.setenv("GITHUB_API_ALLOWED_HOSTS", "evil.example.com")

    with pytest.raises((ValueError, RuntimeError)):
        validate_api_url("https://evil.example.com")

    validate_api_url(
        "https://ghe.example.com/api/v3",
        allowed_hosts=frozenset({"api.github.com", "ghe.example.com"}),
    )


def test_compute_drift_order_insensitive_topics():
    desired = {
        "description": "Some description",
        "homepage": "https://example.com",
        "topics": ["alpha", "beta", "gamma"],
    }
    live = {
        "description": "Some description",
        "homepage": "https://example.com",
        "topics": ["gamma", "beta", "alpha"],
    }

    assert compute_drift(desired, live) == {}


def test_mask_secret_scrubs_token():
    raw = (
        "token=ghp_0123456789abcdefghijklmnopqrstuvwxyz "
        "pat=github_pat_11ABCDEFGHIJKLMNOPQRSTUV "
        "header=Bearer abc123def456 "
        "explicit=super-secret-value"
    )
    masked = mask_secret(raw, "super-secret-value")

    assert "ghp_0123456789" not in masked
    assert "github_pat_11ABCDEF" not in masked
    assert "abc123def456" not in masked
    assert "super-secret-value" not in masked

    secret = "opaque-secret-xyz-987654321"
    secret_bytes = secret.encode("utf-8")
    bodies = [
        b'{"message":"' + secret_bytes + b'"}',
        b"A" * 490 + secret_bytes + b"B" * 50,
        b"A" * 510 + secret_bytes + b"B" * 50,
    ]

    for body in bodies:
        def bad_handler(request, timeout, response_body=body):
            raise urllib.error.HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                Message(),
                io.BytesIO(response_body),
            )

        with pytest.raises(RuntimeError) as excinfo:
            fetch_live_metadata(
                repo=DEFAULT_REPO,
                token=secret,
                opener=_ScriptedOpener(bad_handler),
            )

        message = str(excinfo.value)
        assert secret not in message
        assert "opaque-secret" not in message
        assert excinfo.value.__cause__ is None


def test_decode_error_scrubs_secret_and_suppresses_cause():
    malformed_payloads = [
        b'{"bad": "opaque-secret-xyz"',
        b"\xff\xfeopaque-secret-xyz",
    ]

    for payload in malformed_payloads:
        def handler(request, timeout, response_payload=payload):
            return _FakeResponse(response_payload)

        with pytest.raises(RuntimeError) as excinfo:
            fetch_live_metadata(
                repo=DEFAULT_REPO,
                token="opaque-secret-xyz",
                opener=_ScriptedOpener(handler),
            )

        assert "opaque-secret-xyz" not in str(excinfo.value)
        assert excinfo.value.__cause__ is None


def test_http_client_exception_wrapped_without_cause():
    exceptions = [
        http.client.IncompleteRead(b"part"),
        http.client.BadStatusLine("bad"),
    ]

    for client_error in exceptions:
        def handler(request, timeout, error=client_error):
            raise error

        with pytest.raises(RuntimeError) as excinfo:
            fetch_live_metadata(
                repo=DEFAULT_REPO,
                token="opaque-secret-xyz",
                opener=_ScriptedOpener(handler),
            )

        assert excinfo.value.__cause__ is None


def test_malformed_env_does_not_crash_validate_or_dry_run(monkeypatch):
    monkeypatch.setenv("GITHUB_HTTP_TIMEOUT_S", "abc")
    monkeypatch.setenv("GITHUB_TOKEN", "bad")

    assert main(["--validate"]) == 0
    assert main(["--dry-run"]) == 0


def test_fetch_live_metadata_retries_once_without_auth_on_401():
    def handler(request, timeout):
        if request.get_header("Authorization"):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                Message(),
                None,
            )
        if request.full_url.endswith("/topics"):
            return _FakeResponse({"names": ["a"]})
        return _FakeResponse(
            {"description": "live", "homepage": "https://example.com"}
        )

    opener = _ScriptedOpener(handler)
    live = fetch_live_metadata(
        repo=DEFAULT_REPO,
        token="ghp_0123456789abcdefghijklmnopqrstuvwxyz",
        api_url=DEFAULT_API_URL,
        opener=opener,
        allow_unauth_fallback=True,
    )

    assert len(opener.calls) == 3
    assert opener.calls[0].get_header("Authorization")
    assert opener.calls[1].get_header("Authorization") is None
    assert live["description"] == "live"
    assert live["topics"] == ["a"]

    strict = _ScriptedOpener(handler)
    with pytest.raises(RuntimeError):
        fetch_live_metadata(
            repo=DEFAULT_REPO,
            token="ghp_0123456789abcdefghijklmnopqrstuvwxyz",
            api_url=DEFAULT_API_URL,
            opener=strict,
            allow_unauth_fallback=False,
        )


def test_401_fallback_reports_auth_warning_and_strict_auth_fails(metadata):
    def handler(request, timeout):
        if request.get_header("Authorization"):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                Message(),
                None,
            )
        if request.full_url.endswith("/topics"):
            return _FakeResponse({"names": metadata["topics"]})
        return _FakeResponse(
            {
                "description": metadata["description"],
                "homepage": metadata["homepage"],
            }
        )

    result = check_metadata(
        metadata,
        repo=DEFAULT_REPO,
        token="expired_tok",
        api_url=DEFAULT_API_URL,
        opener=_ScriptedOpener(handler),
    )

    assert result["authenticated"] is False
    assert result["auth_warning"]

    with pytest.raises(_GitHubHTTPError) as excinfo:
        check_metadata(
            metadata,
            repo=DEFAULT_REPO,
            token="expired_tok",
            api_url=DEFAULT_API_URL,
            opener=_ScriptedOpener(handler),
            strict_auth=True,
        )

    assert excinfo.value.status_code == 401


def test_apply_metadata_payloads_and_readback_verification(metadata):
    opener = _StatefulOpener(
        {
            "description": "old",
            "homepage": "https://old.example.com",
            "topics": ["x"],
        }
    )

    result = apply_metadata(
        metadata,
        repo=DEFAULT_REPO,
        token="ghp_0123456789abcdefghijklmnopqrstuvwxyz",
        api_url=DEFAULT_API_URL,
        opener=opener,
    )

    assert result["applied"] is True
    assert result["steps_completed"] == ["patch_repo", "put_topics"]

    methods = [request.get_method() for request in opener.requests]
    assert "PATCH" in methods
    assert "PUT" in methods

    patch_request = next(
        request for request in opener.requests if request.get_method() == "PATCH"
    )
    patch_payload = json.loads(patch_request.data.decode("utf-8"))
    assert patch_payload["description"] == metadata["description"]
    assert patch_payload["homepage"] == metadata["homepage"]

    put_request = next(
        request for request in opener.requests if request.get_method() == "PUT"
    )
    put_payload = json.loads(put_request.data.decode("utf-8"))
    assert put_payload["names"] == metadata["topics"]

    assert opener.state["description"] == metadata["description"]
    assert opener.state["topics"] == metadata["topics"]


def test_malformed_topics_payload_fails_before_write(metadata):
    malformed_payloads = [
        [],
        {},
        {"names": "bad"},
        {"names": [123]},
    ]

    for malformed_payload in malformed_payloads:
        def handler(request, timeout, payload=malformed_payload):
            method = request.get_method()

            if method == "GET" and request.full_url.endswith("/topics"):
                return _FakeResponse(payload)
            if method == "GET":
                return _FakeResponse(
                    {
                        "description": "old",
                        "homepage": "https://old.example.com",
                    }
                )
            if method == "PATCH":
                return _FakeResponse(
                    {
                        "description": metadata["description"],
                        "homepage": metadata["homepage"],
                    }
                )
            if method == "PUT":
                return _FakeResponse({"names": metadata["topics"]})

            raise AssertionError(f"unexpected method: {method}")

        opener = _ScriptedOpener(handler)

        with pytest.raises(RuntimeError):
            apply_metadata(
                metadata,
                repo=DEFAULT_REPO,
                token="ghp_0123456789abcdefghijklmnopqrstuvwxyz",
                api_url=DEFAULT_API_URL,
                opener=opener,
            )

        write_requests = [
            request
            for request in opener.calls
            if request.get_method() in {"PATCH", "PUT"}
        ]
        assert write_requests == []


def test_apply_metadata_reports_partial_apply_on_put_failure(metadata):
    opener = _StatefulOpener(
        {
            "description": "old",
            "homepage": "https://old.example.com",
            "topics": ["x"],
        },
        fail_put=True,
    )

    with pytest.raises(RuntimeError) as excinfo:
        apply_metadata(
            metadata,
            repo=DEFAULT_REPO,
            token="ghp_0123456789abcdefghijklmnopqrstuvwxyz",
            api_url=DEFAULT_API_URL,
            opener=opener,
        )

    assert "partial apply: steps_completed=['patch_repo']" in str(excinfo.value)


def test_cli_check_and_apply_modes(monkeypatch):
    monkeypatch.setenv(
        "GITHUB_TOKEN",
        "ghp_0123456789abcdefghijklmnopqrstuvwxyz",
    )
    desired = load_metadata(DEFAULT_METADATA_PATH)

    in_sync = _StatefulOpener(desired)
    assert main(["--check"], opener=in_sync) == 0

    drifted_state = dict(desired)
    drifted_state["description"] = (
        desired["description"] + " drift"
    )[:MAX_DESCRIPTION_LEN]
    assert main(["--check"], opener=_StatefulOpener(drifted_state)) == 1

    assert main(["--apply"], opener=_StatefulOpener(drifted_state)) == 0


def test_readme_discoverability_and_anti_neuromarkers():
    """README: без типографских маркеров, дублей и с валидными внутренними ссылками."""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert text.count("\u2014") == 0, "README содержит длинное тире (U+2014)"
    assert text.count("\u2192") == 0, "README содержит стрелку (U+2192)"

    assert "suite suite" not in text, "README содержит дубль 'suite suite'"
    assert (
        re.search(r"\.\s+on the other side", text) is None
    ), "README содержит фразу-невромаркер '. on the other side'"

    text_without_fences = re.sub(
        r"^```.*?^```",
        "",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )

    def slugify(heading: str) -> str:
        without_code_ticks = re.sub(r"`([^`]*)`", r"\1", heading)
        stripped = without_code_ticks.strip().lstrip("#").strip().lower()
        without_punctuation = re.sub(r"[^\w\s\-]", "", stripped)
        return re.sub(r"\s", "-", without_punctuation)

    headings = re.findall(
        r"^#{1,6}\s+(.+?)$",
        text_without_fences,
        flags=re.MULTILINE,
    )
    valid_slugs = {slugify(heading) for heading in headings}

    internal_targets = re.findall(
        r"\]\(#([^)\s]+)\)",
        text_without_fences,
    )
    broken = sorted(
        {target for target in internal_targets if target not in valid_slugs}
    )
    assert not broken, f"Битые внутренние ссылки README: {broken}"

    synthetic = (
        "[![Badge](https://img.shields.io/badge/a-b-blue.svg)]"
        "(#non-existent-anchor-slug)"
    )
    synthetic_targets = re.findall(r"\]\(#([^)\s]+)\)", synthetic)

    assert synthetic_targets == ["non-existent-anchor-slug"]
    assert synthetic_targets[0] not in valid_slugs

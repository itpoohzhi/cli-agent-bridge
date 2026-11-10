"""Passthrough-шов к opencode-go: вложенный `/go/v1`, ключ и заголовки из файлов, дефолты тела."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters.passthrough_adapter import PassthroughAdapter, PassthroughLimits  # noqa: E402
from core.backend_adapter import backend_entry_error  # noqa: E402
import test_passthrough_adapter as seam  # noqa: E402

DEEPSEEK = "deepseek-v4.1-flash"
GO_PORT = 10830


class GoStand:
    """Локальный upstream с префиксом `/go/v1` и файлами ключа/заголовков во временном каталоге."""

    def __init__(self, tmp_path: Path, **overrides: Any) -> None:
        self.upstream = seam.FakeUpstream()
        self.upstream.respond = lambda handler, body: seam.FakeUpstream.json(
            handler, {"choices": [{"message": {"content": "ok"}}]}
        )
        self.key_file = tmp_path / "opencode-go.key"
        self.key_file.write_text("go-secret-key\n", encoding="utf-8")
        self.opencode_json = tmp_path / "opencode.json"
        self.opencode_json.write_text(
            json.dumps(
                {
                    "provider": {
                        "opencode-go": {
                            "options": {
                                "headers": {
                                    "x-opencode-org-id": "org-42",
                                    "user-agent": "opencode/1.0",
                                    "x-ignored": "must-not-leak",
                                }
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        config: dict[str, Any] = {
            "kind": "passthrough",
            "base_url": "http://127.0.0.1:%d/go/v1" % self.upstream.port,
            "max_concurrent": 2,
            "api_key_ref": "file:%s" % self.key_file,
            "headers_from_json": {
                "file": str(self.opencode_json),
                "json_path": ["provider", "opencode-go", "options", "headers"],
                "pick": ["x-opencode-org-id", "User-Agent"],
            },
            "per_request_headers": {"x-opencode-session": "{uuid4}"},
            "default_body_extra": {"thinking": {"type": "disabled"}},
        }
        config.update(overrides)
        self.adapter = PassthroughAdapter(
            "opencode-go",
            config,
            lambda: {},
            None,
            limits=PassthroughLimits(),
            is_hub_key=lambda token: token == "hub-key",
        )

    def call(self, body: dict[str, Any], headers: dict[str, str] | None = None) -> dict:
        sink = seam.CollectSink()
        self.adapter.handle(
            path="/v1/chat/completions",
            raw_body=json.dumps(body).encode("utf-8"),
            request=body,
            headers=headers or {},
            sink=sink,
        )
        assert sink.status == 200
        sent = self.upstream.requests[-1]
        return {
            "path": sent["path"],
            "headers": {k.lower(): v for k, v in sent["headers"].items()},
            "body": json.loads(sent["body"]),
        }

    def close(self) -> None:
        self.adapter.shutdown()
        self.upstream.close()


@pytest.fixture
def go(tmp_path: Path):
    stand = GoStand(tmp_path)
    yield stand
    stand.close()


def _adapter_for(base_url: str) -> PassthroughAdapter:
    return PassthroughAdapter(
        "opencode-go",
        {"kind": "passthrough", "base_url": base_url, "max_concurrent": 1},
        lambda: {},
        None,
        limits=PassthroughLimits(),
    )


def test_nested_go_v1_base_url_is_accepted() -> None:
    adapter = _adapter_for("http://127.0.0.1:%d/go/v1" % GO_PORT)
    try:
        assert adapter.config["base_url"].endswith(":10830/go/v1")
    finally:
        adapter.shutdown()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://127.0.0.1:10830/go",
        "http://127.0.0.1:10830/go/v2",
        "http://127.0.0.1:10830/GO/v1",
        "https://127.0.0.1:10830/go/v1",
        "http://example.com:10830/go/v1",
        "http://127.0.0.1:10830/go/v1/extra",
    ],
)
def test_non_loopback_or_non_v1_base_url_is_rejected(base_url: str) -> None:
    with pytest.raises(ValueError, match="backend_base_url_invalid"):
        _adapter_for(base_url)


def test_backend_entry_validation_accepts_nested_prefix_and_upstream_params() -> None:
    entry = {
        "kind": "passthrough",
        "enabled": True,
        "required": False,
        "owned_by": "opencode-go",
        "max_concurrent": 1,
        "base_url": "http://127.0.0.1:10830/go/v1",
        "api_key_ref": "file:~/.config/opencode/opencode-go.key",
        "headers_from_json": {
            "file": "~/.config/opencode/opencode.json",
            "json_path": ["provider", "opencode-go", "options", "headers"],
            "pick": ["x-opencode-org-id"],
        },
        "per_request_headers": {"x-opencode-session": "{uuid4}"},
        "default_body_extra": {"thinking": {"type": "disabled"}},
    }
    assert (
        backend_entry_error("opencode-go", entry, {"passthrough": PassthroughAdapter})
        == ""
    )
    broken = dict(entry, api_key_ref="~/no-file-prefix")
    assert backend_entry_error(
        "opencode-go", broken, {"passthrough": PassthroughAdapter}
    ) == ("backend_api_key_ref_invalid")


def test_request_reaches_nested_prefix_with_key_and_file_headers(go: GoStand) -> None:
    sent = go.call({"model": DEEPSEEK, "messages": []})
    assert sent["path"] == "/go/v1/chat/completions"
    assert sent["headers"]["authorization"] == "Bearer go-secret-key"
    assert sent["headers"]["x-opencode-org-id"] == "org-42"
    assert sent["headers"]["user-agent"] == "opencode/1.0"
    assert "x-ignored" not in sent["headers"]


def test_key_ref_replaces_client_credentials(go: GoStand) -> None:
    sent = go.call(
        {"model": DEEPSEEK},
        headers={"Authorization": "Bearer hub-key", "X-Api-Key": "client-x"},
    )
    assert sent["headers"]["authorization"] == "Bearer go-secret-key"
    assert "x-api-key" not in sent["headers"]


def test_key_ref_is_reread_on_every_request(go: GoStand) -> None:
    assert go.call({"model": DEEPSEEK})["headers"]["authorization"].endswith(
        "go-secret-key"
    )
    go.key_file.write_text("rotated-key", encoding="utf-8")
    assert (
        go.call({"model": DEEPSEEK})["headers"]["authorization"] == "Bearer rotated-key"
    )


def test_unreadable_key_ref_keeps_client_credentials(go: GoStand) -> None:
    go.key_file.unlink()
    sent = go.call({"model": DEEPSEEK}, headers={"Authorization": "Bearer client-own"})
    assert sent["headers"]["authorization"] == "Bearer client-own"


def test_per_request_session_header_is_fresh_uuid4(go: GoStand) -> None:
    first = go.call({"model": DEEPSEEK})["headers"]["x-opencode-session"]
    second = go.call({"model": DEEPSEEK})["headers"]["x-opencode-session"]
    assert first != second
    for value in (first, second):
        assert uuid.UUID(value).version == 4
        assert "{uuid4}" not in value


def test_client_cannot_override_per_request_or_file_headers(go: GoStand) -> None:
    sent = go.call(
        {"model": DEEPSEEK},
        headers={
            "x-opencode-session": "client-session",
            "X-Opencode-Org-Id": "evil-org",
        },
    )
    assert sent["headers"]["x-opencode-session"] != "client-session"
    assert sent["headers"]["x-opencode-org-id"] == "org-42"


def test_default_body_extra_disables_thinking(go: GoStand) -> None:
    sent = go.call({"model": DEEPSEEK, "messages": [{"role": "user", "content": "hi"}]})
    assert sent["body"]["thinking"] == {"type": "disabled"}
    assert sent["body"]["model"] == DEEPSEEK
    assert sent["body"]["messages"] == [{"role": "user", "content": "hi"}]


def test_explicit_thinking_in_request_is_not_overridden(go: GoStand) -> None:
    sent = go.call({"model": DEEPSEEK, "thinking": {"type": "enabled"}})
    assert sent["body"]["thinking"] == {"type": "enabled"}


@pytest.mark.parametrize("effort", ["high", "max", "low"])
def test_requested_reasoning_effort_skips_disabled_default(
    go: GoStand, effort: str
) -> None:
    sent = go.call({"model": DEEPSEEK, "reasoning_effort": effort})
    assert "thinking" not in sent["body"]
    assert sent["body"]["reasoning_effort"] == effort


@pytest.mark.parametrize("effort", ["off", "none", ""])
def test_off_reasoning_effort_keeps_disabled_default(go: GoStand, effort: str) -> None:
    sent = go.call({"model": DEEPSEEK, "reasoning_effort": effort})
    assert sent["body"]["thinking"] == {"type": "disabled"}


def test_body_without_upstream_params_is_forwarded_verbatim(tmp_path: Path) -> None:
    stand = GoStand(
        tmp_path,
        api_key_ref=None,
        headers_from_json=None,
        per_request_headers=None,
        default_body_extra=None,
    )
    try:
        raw = b'{"model":  "m",   "messages": []}'
        sink = seam.CollectSink()
        stand.adapter.handle(
            path="/v1/chat/completions", raw_body=raw, request={}, headers={}, sink=sink
        )
        assert stand.upstream.requests[-1]["body"] == raw
        sent_headers = {k.lower() for k in stand.upstream.requests[-1]["headers"]}
        assert not sent_headers & {
            "authorization",
            "x-opencode-session",
            "x-opencode-org-id",
        }
    finally:
        stand.close()


def test_missing_headers_file_is_tolerated(go: GoStand) -> None:
    go.opencode_json.unlink()
    sent = go.call({"model": DEEPSEEK})
    assert "x-opencode-org-id" not in sent["headers"]
    assert sent["headers"]["authorization"] == "Bearer go-secret-key"


def test_compiled_fleet_routes_deepseek_through_opencode_go_adapter() -> None:
    fleet = json.loads((Path(server.ROOT) / "fleet.json").read_text(encoding="utf-8"))
    backend = fleet["backends"]["opencode-go"]
    catalog = server._build_catalog(fleet)
    assert catalog["models"][DEEPSEEK]["backend"] == "opencode-go"
    registry = server.AdapterRegistry.from_fleet(
        catalog, server.ADAPTER_KINDS, lambda: catalog, server
    )
    try:
        adapter = registry.adapter_for_model(DEEPSEEK)
        assert adapter.id == "opencode-go"
        assert adapter.kind == "passthrough"
        for key in (
            "base_url",
            "api_key_ref",
            "headers_from_json",
            "per_request_headers",
            "default_body_extra",
        ):
            assert adapter.config[key] == backend[key], key
    finally:
        for item in registry.adapters():
            item.shutdown()

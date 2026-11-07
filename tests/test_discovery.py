"""L1-тесты discovery (architecture-spec §4.2): http/cli/static, фильтры, секреты, PGID, кэш."""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core import discovery as disc  # noqa: E402
from core.provider_manifest import (  # noqa: E402
    BridgeTransport,
    DiscoveryConfig,
    FingerprintConfig,
    ProviderManifest,
    TransportConfig,
)


class FakeUpstream:
    """In-process HTTP-апстрим на 127.0.0.1:0."""

    def __init__(self) -> None:
        self.routes: Dict[str, Tuple[int, bytes, Dict[str, str]]] = {}
        self.requests: List[Dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                outer.requests.append(
                    {"path": self.path, "auth": self.headers.get("Authorization")}
                )
                status, body, headers = outer.routes.get(self.path, (404, b"{}", {}))
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return "http://127.0.0.1:%d/v1" % self.server.server_address[1]

    def set_json(self, path: str, doc: Any, status: int = 200) -> None:
        self.routes[path] = (status, json.dumps(doc).encode("utf-8"), {})

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def upstream():
    server = FakeUpstream()
    yield server
    server.close()


@pytest.fixture()
def env(tmp_path: Path) -> Dict[str, str]:
    return {
        "BRIDGE_STATE_DIR": str(tmp_path / "state"),
        "BRIDGE_DIRECT_EXEC_DIRS": str(tmp_path / "bin"),
        "BRIDGE_DISCOVERY_KILL_GRACE_S": "0.2",
        "PROV_BRIDGE_KEY": "secret-token-123",
        "PATH": os.environ.get("PATH", ""),
    }


def make_manifest(
    discovery: DiscoveryConfig,
    base_url: Optional[str] = None,
    fingerprint: Optional[FingerprintConfig] = None,
) -> ProviderManifest:
    bridge = BridgeTransport(base_url=base_url, api_key_env="PROV_BRIDGE_KEY")
    return ProviderManifest(
        provider_id="prov",
        kind="passthrough",
        owned_by="acme",
        transport=TransportConfig(bridge=bridge),
        discovery=discovery,
        fingerprint=fingerprint or FingerprintConfig(),
    )


def http_manifest(upstream: FakeUpstream, **extra: Any) -> ProviderManifest:
    cfg = DiscoveryConfig(
        method="http",
        http={
            "path": "/models",
            "id_field": "data[].id",
            "meta_fields": {"owned_by": "owned_by"},
        },
        timeout_s=3.0,
        **extra,
    )
    return make_manifest(cfg, upstream.base_url)


def write_script(directory: Path, name: str, body: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("#!%s\n%s" % (sys.executable, body), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def cli_manifest(
    argv: List[str], fmt: str = "lines", timeout_s: float = 3.0, **extra: Any
):
    cfg = DiscoveryConfig(
        method="cli",
        cli={"argv": argv, "parse": {"format": fmt}},
        timeout_s=timeout_s,
        **extra,
    )
    return make_manifest(cfg)


# ---- http ---------------------------------------------------------------------------------


def test_http_discovery_ids_meta_and_bearer(upstream, env):
    upstream.set_json(
        "/v1/models",
        {"data": [{"id": "m-a", "owned_by": "x"}, {"id": "m-b-free"}, {"id": "m-c"}]},
    )
    result = disc.discover(http_manifest(upstream), env=env)
    assert result.error is None
    assert result.model_ids == ("m-a", "m-c")
    assert result.meta["m-a"] == {"owned_by": "x"}
    assert upstream.requests[0]["auth"] == "Bearer secret-token-123"
    assert len(result.fingerprint_sha256) == 64


def test_http_bypasses_environment_proxy(upstream, env, monkeypatch):
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    upstream.set_json("/v1/models", {"data": [{"id": "m-a"}]})
    assert disc.discover(http_manifest(upstream), env=env).model_ids == ("m-a",)


def test_http_redirect_is_not_followed(upstream, env):
    upstream.routes["/v1/models"] = (302, b"", {"Location": "http://127.0.0.1:1/x"})
    result = disc.discover(http_manifest(upstream), env=env)
    assert result.error == "discovery_http_status_302"
    assert result.model_ids == ()


@pytest.mark.parametrize(
    "status,slug",
    [(500, "discovery_http_status_500"), (401, "discovery_http_status_401")],
)
def test_http_status_error_never_raises(upstream, env, status, slug):
    upstream.set_json("/v1/models", {"error": "x"}, status=status)
    result = disc.discover(http_manifest(upstream), env=env)
    assert (result.error, result.model_ids, dict(result.meta)) == (slug, (), {})


def test_http_connection_refused_and_bad_json(upstream, env):
    upstream.routes["/v1/models"] = (200, b"not-json", {})
    assert (
        disc.discover(http_manifest(upstream), env=env).error
        == "discovery_parse_failed"
    )
    upstream.close()
    result = disc.discover(http_manifest(upstream), env=env)
    assert result.error is not None and result.model_ids == ()


def test_http_body_cap(upstream, env):
    upstream.set_json(
        "/v1/models", {"data": [{"id": "m-%03d" % i} for i in range(200)]}
    )
    env = dict(env, BRIDGE_DISCOVERY_MAX_BYTES="100")
    assert (
        disc.discover(http_manifest(upstream), env=env).error
        == "discovery_output_too_large"
    )


def test_http_scheme_must_be_http(env):
    cfg = DiscoveryConfig(method="http", http={"path": "/m"}, timeout_s=1.0)
    manifest = make_manifest(cfg, "file:///etc")
    assert disc.discover(manifest, env=env).error == "discovery_http_scheme_invalid"


def test_http_missing_base_url_is_error(env):
    cfg = DiscoveryConfig(method="http", http={"path": "/m"}, timeout_s=1.0)
    assert (
        disc.discover(make_manifest(cfg, None), env=env).error
        == "discovery_base_url_missing"
    )


def test_discover_never_raises_on_garbage_manifest(env):
    result = disc.discover(None, env=env)  # type: ignore[arg-type]
    assert result.error == "discovery_internal_error" and result.model_ids == ()


# ---- static, фильтры, канонические id ----------------------------------------------------------


def test_static_discovery_and_dedupe_keeps_order(env):
    cfg = DiscoveryConfig(method="static", static=("b", "a", "b", "c"))
    result = disc.discover(make_manifest(cfg), env=env)
    assert result.model_ids == ("b", "a", "c") and result.error is None


def test_include_exclude_globs(env):
    cfg = DiscoveryConfig(
        method="static",
        static=("g-1", "g-2-mini", "h-1", "g-3"),
        include=("g-*",),
        exclude=("*-mini",),
    )
    assert disc.discover(make_manifest(cfg), env=env).model_ids == ("g-1", "g-3")


def test_empty_include_means_all_and_exclude_applies(env):
    cfg = DiscoveryConfig(method="static", static=("a", "b"), exclude=("b",))
    assert disc.discover(make_manifest(cfg), env=env).model_ids == ("a",)


def test_canonical_id_strip_suffix_and_map(env):
    cfg = DiscoveryConfig(
        method="static",
        static=("alpha-latest", "beta", "gamma-raw"),
        strip_suffixes=("-latest",),
        canonical_map={"gamma-raw": "gamma"},
    )
    assert disc.discover(make_manifest(cfg), env=env).model_ids == (
        "alpha",
        "beta",
        "gamma",
    )


def test_free_suffix_always_dropped_even_without_config(env):
    cfg = DiscoveryConfig(method="static", static=("ok", "x-free", "y-free-extra"))
    assert disc.discover(make_manifest(cfg), env=env).model_ids == (
        "ok",
        "y-free-extra",
    )


def test_free_dropped_after_canonicalization(env):
    cfg = DiscoveryConfig(
        method="static",
        static=("p-free", "q-free"),
        strip_suffixes=("-free",),
        canonical_map={"q": "q-free"},
    )
    # `p-free` -> `p` (канонический id без суффикса), `q-free` -> `q` -> карта `q-free` -> drop
    assert disc.discover(make_manifest(cfg), env=env).model_ids == ("p",)


def test_ids_not_matching_arg_pattern_are_dropped(env):
    cfg = DiscoveryConfig(method="static", static=("good-1", "bad id", "$(x)", ";rm"))
    assert disc.discover(make_manifest(cfg), env=env).model_ids == ("good-1",)


# ---- cli ----------------------------------------------------------------------------------------


def test_cli_lines_and_json(tmp_path, env):
    script = write_script(tmp_path / "bin", "lines.py", "print('m-1')\nprint('m-2')\n")
    result = disc.discover(cli_manifest([script]), env=env)
    assert result.error is None and result.model_ids == ("m-1", "m-2")

    jscript = write_script(
        tmp_path / "bin",
        "j.py",
        "import json\nprint(json.dumps({'items': [{'name': 'j-1'}, {'name': 'j-2'}]}))\n",
    )
    manifest = make_manifest(
        DiscoveryConfig(
            method="cli",
            cli={
                "argv": [jscript],
                "parse": {"format": "json", "id_field": "items[].name"},
            },
            timeout_s=3.0,
        )
    )
    assert disc.discover(manifest, env=env).model_ids == ("j-1", "j-2")


def test_cli_line_regex(tmp_path, env):
    script = write_script(
        tmp_path / "bin", "r.py", "print('* model: aa-1 (x)')\nprint('noise')\n"
    )
    cfg = DiscoveryConfig(
        method="cli",
        cli={
            "argv": [script],
            "parse": {"format": "lines", "line_regex": r"model: (\S+)"},
        },
        timeout_s=3.0,
    )
    assert disc.discover(make_manifest(cfg), env=env).model_ids == ("aa-1",)


def test_cli_child_env_has_no_bridge_secrets(tmp_path, env):
    script = write_script(
        tmp_path / "bin", "env.py", "import os\nprint('\\n'.join(sorted(os.environ)))\n"
    )
    leaky = dict(
        env,
        BRIDGE_KEY="k1",
        DEMO_BRIDGE_KEY="k2",
        CODEX_LB_API_KEY="k3",
        KEEP_ME_VISIBLE="1",
    )
    result = disc.discover(cli_manifest([script]), env=leaky)
    assert result.error is None
    names = set(result.model_ids)
    assert "KEEP_ME_VISIBLE" in names
    assert not names & {
        "BRIDGE_KEY",
        "DEMO_BRIDGE_KEY",
        "CODEX_LB_API_KEY",
        "PROV_BRIDGE_KEY",
    }


def test_cli_runs_in_fresh_tempdir_and_own_pgid(tmp_path, env):
    script = write_script(
        tmp_path / "bin",
        "cwd.py",
        "import os\nprint(os.getcwd())\nprint('pgid-%s' % ('own' if os.getpgrp() == os.getpid() else 'shared'))\n",
    )
    result = disc.discover(cli_manifest([script]), env=env)
    assert result.error is None
    cwd = next(i for i in result.model_ids if "bridge-discovery-" in i)
    assert Path(cwd).name.startswith("bridge-discovery-")
    assert not Path(cwd).exists()  # убран после прогона
    assert "pgid-own" in result.model_ids


def test_cli_executable_outside_allowlist_is_refused(tmp_path, env):
    script = write_script(tmp_path / "elsewhere", "x.py", "print('m')\n")
    result = disc.discover(cli_manifest([script]), env=env)
    assert result.error == "discovery_executable_forbidden" and result.model_ids == ()


def test_cli_nonzero_exit_is_error(tmp_path, env):
    script = write_script(
        tmp_path / "bin", "bad.py", "import sys\nprint('m')\nsys.exit(3)\n"
    )
    assert (
        disc.discover(cli_manifest([script]), env=env).error == "discovery_cli_failed"
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_cli_timeout_kills_whole_process_group(tmp_path, env):
    pid_file = tmp_path / "child.pid"
    body = (
        "import subprocess, sys, time, signal\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import signal,time;signal.signal(signal.SIGTERM, signal.SIG_IGN);time.sleep(60)'])\n"
        "open(%r, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n" % str(pid_file)
    )
    script = write_script(tmp_path / "bin", "hang.py", body)
    started = time.monotonic()
    result = disc.discover(cli_manifest([script], timeout_s=0.6), env=env)
    assert result.error == "discovery_timeout" and result.model_ids == ()
    assert time.monotonic() - started < 10
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(pid), "потомок группы пережил таймаут"


def test_cli_sliding_activity_window_extends_deadline(tmp_path, env):
    body = (
        "import sys, time\n"
        "for i in range(6):\n"
        "    print('m-%d' % i, flush=True)\n"
        "    time.sleep(0.25)\n"
    )
    script = write_script(tmp_path / "bin", "slow.py", body)
    # общее время ~1.5 c > idle 0.8 c, но каждый чанк сдвигает дедлайн
    result = disc.discover(cli_manifest([script], timeout_s=0.8), env=env)
    assert result.error is None and len(result.model_ids) == 6


def test_cli_output_cap(tmp_path, env):
    script = write_script(
        tmp_path / "bin",
        "big.py",
        "import sys\nfor i in range(100000):\n    print('model-%d' % i)\n",
    )
    env = dict(env, BRIDGE_DISCOVERY_MAX_BYTES="2048")
    assert (
        disc.discover(cli_manifest([script]), env=env).error
        == "discovery_output_too_large"
    )


# ---- fingerprint ----------------------------------------------------------------------------------


def test_fingerprint_constant_when_nothing_configured(env):
    cfg = DiscoveryConfig(method="static", static=("a",))
    first = disc.discover(make_manifest(cfg), env=env).fingerprint_sha256
    again = disc.discover(make_manifest(cfg), env=env).fingerprint_sha256
    import hashlib

    assert first == again == hashlib.sha256(b"no-fingerprint").hexdigest()


def test_fingerprint_follows_binary_content_and_version_cmd(tmp_path, env):
    binary = tmp_path / "bin" / "tool"
    binary.parent.mkdir()
    binary.write_bytes(b"v1")
    ver = write_script(tmp_path / "bin", "ver.py", "print('1.2.3')\n")
    cfg = DiscoveryConfig(method="static", static=("a",))

    def fp(**kw: Any) -> str:
        manifest = make_manifest(
            cfg, fingerprint=FingerprintConfig(binary_path=str(binary), **kw)
        )
        return disc.discover(manifest, env=env).fingerprint_sha256

    base = fp()
    assert base == fp()
    with_version = fp(version_cmd=(ver,))
    assert with_version != base
    binary.write_bytes(b"v2-different")
    assert fp() != base


# ---- кэш ------------------------------------------------------------------------------------------


def test_cache_ttl_and_force(upstream, env):
    upstream.set_json("/v1/models", {"data": [{"id": "m-a"}]})
    manifest = http_manifest(upstream, refresh_interval_s=100.0)
    clock = {"now": 1000.0}

    def run(**kw: Any):
        return disc.discover(manifest, env=env, clock=lambda: clock["now"], **kw)

    assert run().model_ids == ("m-a",)
    clock["now"] += 50
    upstream.set_json("/v1/models", {"data": [{"id": "m-a"}, {"id": "m-b"}]})
    assert run().model_ids == ("m-a",)  # из кэша
    assert len(upstream.requests) == 1
    clock["now"] += 51  # TTL истёк
    assert run().model_ids == ("m-a", "m-b")
    assert len(upstream.requests) == 2
    assert run(force=True).model_ids == ("m-a", "m-b")
    assert len(upstream.requests) == 3
    cache = json.loads(
        Path(env["BRIDGE_STATE_DIR"], "discovery-cache.json").read_text()
    )
    assert cache["schema"] == 1 and len(cache["entries"]) == 1
    assert next(iter(cache["entries"])).startswith("prov|")


def test_cache_keyed_by_fingerprint(tmp_path, upstream, env):
    upstream.set_json("/v1/models", {"data": [{"id": "m-a"}]})
    binary = tmp_path / "tool"
    binary.write_bytes(b"one")
    cfg = DiscoveryConfig(
        method="http", http={"path": "/models"}, timeout_s=3.0, refresh_interval_s=1e6
    )
    manifest = make_manifest(
        cfg, upstream.base_url, FingerprintConfig(binary_path=str(binary))
    )
    disc.discover(manifest, env=env)
    disc.discover(manifest, env=env)
    assert len(upstream.requests) == 1
    binary.write_bytes(b"two-changed")
    disc.discover(manifest, env=env)
    assert len(upstream.requests) == 2


def test_errors_are_not_cached(upstream, env):
    manifest = http_manifest(upstream)
    upstream.set_json("/v1/models", {}, status=503)
    assert disc.discover(manifest, env=env).error == "discovery_http_status_503"
    upstream.set_json("/v1/models", {"data": [{"id": "m-a"}]})
    assert disc.discover(manifest, env=env).model_ids == ("m-a",)


def test_discover_all_isolates_failures(upstream, env):
    upstream.set_json("/v1/models", {"data": [{"id": "m-a"}]})
    good = http_manifest(upstream)
    bad_cfg = DiscoveryConfig(method="http", http={"path": "/models"}, timeout_s=1.0)
    bad = ProviderManifest(
        provider_id="bad",
        kind="passthrough",
        owned_by="x",
        transport=TransportConfig(
            bridge=BridgeTransport(base_url="http://127.0.0.1:1/v1")
        ),
        discovery=bad_cfg,
    )
    off = ProviderManifest(
        provider_id="off",
        kind="passthrough",
        owned_by="x",
        enabled=False,
        discovery=DiscoveryConfig(method="static", static=("z",)),
    )
    results = disc.discover_all([bad, good, off], env)
    assert list(results) == ["bad", "prov"]
    assert results["bad"].error is not None and results["bad"].model_ids == ()
    assert results["prov"].model_ids == ("m-a",)


def test_jsonpath_lite_helpers():
    doc = {"a": {"list": [{"id": "x", "n": {"k": 1}}, {"id": 5}, {"nope": 1}]}}
    pairs = disc.extract_ids_and_meta(doc, "a.list[].id", {"k": "n.k"})
    assert pairs == [("x", {"k": 1})]
    assert disc.extract_ids_and_meta({"m": ["p", "q"]}, "m[]") == [("p", {}), ("q", {})]
    assert disc.extract_ids_and_meta(["p"], "[]") == [("p", {})]

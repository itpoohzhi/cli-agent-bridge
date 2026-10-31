"""CLI `agent-browser` (tools/agent_browser.py, ADR-0016) против фейкового CDP-сервера на loopback.

Фейк — стандартная библиотека: HTTP `/json/list` и WebSocket (RFC 6455) на одном порту.
Настоящий браузер и внешняя сеть не используются.
"""

import base64
import hashlib
import json
import os
import socket
import socketserver
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import agent_browser  # noqa: E402
import server  # noqa: E402

TOOL = ROOT / "tools" / "agent_browser.py"
GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


def _read_frame(sock):
    def exact(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError
            buf += chunk
        return buf

    b1, b2 = exact(2)
    size = b2 & 0x7F
    if size == 126:
        (size,) = struct.unpack(">H", exact(2))
    elif size == 127:
        (size,) = struct.unpack(">Q", exact(8))
    mask = exact(4)
    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(exact(size)))
    return b1 & 0x0F, payload


def _send_frame(sock, text):
    payload = text.encode()
    if len(payload) < 126:
        header = bytes([0x81, len(payload)])
    elif len(payload) < 1 << 16:
        header = bytes([0x81, 126]) + struct.pack(">H", len(payload))
    else:
        header = bytes([0x81, 127]) + struct.pack(">Q", len(payload))
    sock.sendall(header + payload)


class FakeCdp(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, targets=None, silent=False, ping_first=False, no_load=False):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.port = self.server_address[1]
        self.silent = silent
        self.ping_first = ping_first
        self.no_load = no_load
        self.calls = []  # (method, params)
        self.requests = []  # HTTP paths
        self.targets = targets

    def page_ws(self):
        return f"ws://127.0.0.1:{self.port}/devtools/page/P1"

    def list_json(self):
        if self.targets is not None:
            return self.targets
        return [
            {"type": "background_page", "webSocketDebuggerUrl": "ws://127.0.0.1:1/x"},
            {"type": "page", "webSocketDebuggerUrl": self.page_ws()},
        ]


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        sock, srv = self.request, self.server
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                return
            data += chunk
        head = data.decode("latin-1").split("\r\n")
        path = head[0].split(" ")[1]
        headers = {
            k.strip().lower(): v.strip()
            for k, _, v in (line.partition(":") for line in head[1:] if line)
        }
        if headers.get("upgrade", "").lower() != "websocket":
            srv.requests.append(path)
            body = json.dumps(srv.list_json()).encode()
            sock.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            return
        srv.requests.append("WS " + path)
        accept = base64.b64encode(
            hashlib.sha1(headers["sec-websocket-key"].encode() + GUID).digest()
        ).decode()
        sock.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
            b"Connection: Upgrade\r\nSec-WebSocket-Accept: "
            + accept.encode()
            + b"\r\n\r\n"
        )
        if srv.silent:
            threading.Event().wait(5)
            return
        if srv.ping_first:
            sock.sendall(bytes([0x89, 0]))
        try:
            while True:
                opcode, payload = _read_frame(sock)
                if opcode == 0x8:
                    return
                if opcode != 0x1:
                    continue
                msg = json.loads(payload)
                self.answer(sock, srv, msg)
        except (ConnectionError, OSError):
            return

    def answer(self, sock, srv, msg):
        method, params, mid = msg["method"], msg.get("params", {}), msg["id"]
        srv.calls.append((method, params))
        result = {}
        if method == "Runtime.evaluate":
            expr = params["expression"]
            if expr == "document.title":
                result = {"result": {"type": "string", "value": "Fake Title"}}
            elif expr == "boom":
                result = {
                    "result": {"type": "object"},
                    "exceptionDetails": {
                        "text": "Uncaught",
                        "exception": {"description": "ReferenceError: boom"},
                    },
                }
            elif expr == "obj":
                result = {"result": {"type": "object", "value": {"a": [1, 2]}}}
            elif expr == "undef":
                result = {"result": {"type": "undefined"}}
            else:
                result = {"result": {"type": "number", "value": 2}}
        elif method == "Page.navigate":
            result = {"frameId": "F1"}
        elif method == "Page.captureScreenshot":
            result = {"data": base64.b64encode(PNG).decode()}
        if method == "Page.navigate":
            _send_frame(
                sock, json.dumps({"method": "Page.frameNavigated", "params": {}})
            )
        _send_frame(sock, json.dumps({"id": mid, "result": result}))
        if method == "Page.navigate" and not srv.no_load:
            _send_frame(
                sock, json.dumps({"method": "Page.loadEventFired", "params": {}})
            )


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        patcher = mock.patch.dict(
            os.environ,
            {
                "BRIDGE_CDP_DISCOVERY_PATH": str(self.dir / "none"),
                "BRIDGE_CDP_TIMEOUT_S": "5",
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("AGENT_BROWSER_CDP", None)

    def cdp(self, **kw):
        srv = FakeCdp(**kw)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv

    def run_cli(self, *args, env=None):
        """Настоящий subprocess CLI; `-I` — интерпретатор изолирован от cwd/PYTHON*."""
        full_env = dict(os.environ)
        full_env.update(env or {})
        return subprocess.run(
            [sys.executable, "-I", str(TOOL), *args],
            capture_output=True,
            text=True,
            timeout=30,
            env=full_env,
            cwd=self.tmp.name,
        )


class TestCommands(CliCase):
    def test_help(self):
        out = self.run_cli("--help")
        self.assertEqual(out.returncode, 0)
        for word in ("eval", "title", "navigate", "screenshot", "--cdp"):
            self.assertIn(word, out.stdout)
        sub = self.run_cli("eval", "--help")
        self.assertEqual(sub.returncode, 0)

    def test_usage_error_is_exit_2(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli("bogus").returncode, 2)

    def test_eval_via_page_ws_and_http_and_browser_ws(self):
        srv = self.cdp()
        for cdp in (
            srv.page_ws(),
            f"http://127.0.0.1:{srv.port}",
            f"ws://127.0.0.1:{srv.port}/devtools/browser/bb-cc",
        ):
            out = self.run_cli("--cdp", cdp, "eval", "1+1")
            self.assertEqual(
                (out.returncode, out.stdout), (0, "2\n"), (cdp, out.stderr)
            )
        evals = [p for m, p in srv.calls if m == "Runtime.evaluate"]
        self.assertEqual(evals[0]["expression"], "1+1")
        self.assertTrue(evals[0]["returnByValue"])
        # для http и browser-ws страница найдена через /json/list
        self.assertEqual(srv.requests.count("/json/list"), 2)

    def test_eval_value_kinds_and_exception(self):
        srv = self.cdp()
        cdp = srv.page_ws()
        self.assertEqual(
            self.run_cli("--cdp", cdp, "eval", "obj").stdout, '{"a": [1, 2]}\n'
        )
        self.assertEqual(
            self.run_cli("--cdp", cdp, "eval", "undef").stdout, "undefined\n"
        )
        out = self.run_cli("--cdp", cdp, "eval", "boom")
        self.assertEqual(out.returncode, 1)
        self.assertIn("ReferenceError: boom", out.stderr)
        self.assertEqual(out.stdout, "")

    def test_title(self):
        srv = self.cdp()
        out = self.run_cli("--cdp", srv.page_ws(), "title")
        self.assertEqual((out.returncode, out.stdout), (0, "Fake Title\n"))

    def test_cdp_from_environment(self):
        srv = self.cdp()
        out = self.run_cli("title", env={"AGENT_BROWSER_CDP": srv.page_ws()})
        self.assertEqual((out.returncode, out.stdout), (0, "Fake Title\n"))

    def test_navigate_waits_for_load_and_rejects_bad_scheme(self):
        srv = self.cdp()
        out = self.run_cli(
            "--cdp", srv.page_ws(), "navigate", "https://example.invalid/x"
        )
        self.assertEqual(
            (out.returncode, out.stdout), (0, "https://example.invalid/x\n")
        )
        methods = [m for m, _ in srv.calls]
        self.assertEqual(methods, ["Page.enable", "Page.navigate"])
        bad = self.run_cli("--cdp", srv.page_ws(), "navigate", "javascript:alert(1)")
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(len(srv.calls), 2)  # до CDP не дошло

    def test_screenshot_writes_private_png(self):
        srv = self.cdp()
        target = self.dir / "shot.png"
        out = self.run_cli("--cdp", srv.page_ws(), "screenshot", str(target))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(target.read_bytes(), PNG)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_navigate_without_load_event_is_exit_1(self):
        srv = self.cdp(no_load=True)
        out = self.run_cli(
            "--cdp",
            srv.page_ws(),
            "--timeout",
            "0.5",
            "navigate",
            "https://example.invalid/x",
        )
        self.assertEqual(out.returncode, 1)
        self.assertEqual(out.stdout, "")
        self.assertIn("navigate", out.stderr)

    def test_navigate_file_scheme_is_rejected(self):
        srv = self.cdp()
        for url in ("file:///etc/passwd", "FILE:///etc/hosts"):
            out = self.run_cli("--cdp", srv.page_ws(), "navigate", url)
            self.assertEqual(out.returncode, 2, url)
        self.assertEqual(srv.calls, [])
        self.assertEqual(
            agent_browser._NAVIGATE_SCHEMES, frozenset({"http", "https", "about"})
        )

    def test_screenshot_tightens_preexisting_world_readable_file(self):
        srv = self.cdp()
        target = self.dir / "old.png"
        target.write_bytes(b"old-content-longer-than-new-png-payload-xxxxxxxxxxxxxxxx")
        os.chmod(target, 0o644)
        out = self.run_cli("--cdp", srv.page_ws(), "screenshot", str(target))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(target.read_bytes(), PNG)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_ping_frames_are_answered(self):
        srv = self.cdp(ping_first=True)
        out = self.run_cli("--cdp", srv.page_ws(), "title")
        self.assertEqual((out.returncode, out.stdout), (0, "Fake Title\n"))

    def test_timeout_exit_1_without_hanging(self):
        srv = self.cdp(silent=True)
        out = self.run_cli("--cdp", srv.page_ws(), "--timeout", "0.5", "title")
        self.assertEqual(out.returncode, 1)
        self.assertIn("timeout", out.stderr)

    def test_connection_refused_is_exit_1_and_masks_url(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        url = f"ws://127.0.0.1:{port}/devtools/page/SECRET-ID"
        out = self.run_cli("--cdp", url, "title")
        self.assertEqual(out.returncode, 1)
        self.assertNotIn("SECRET-ID", out.stderr + out.stdout)


class TestLoopbackValidation(CliCase):
    def test_external_cdp_argument_rejected_before_any_connection(self):
        srv = self.cdp()
        for url in (
            "ws://evil.example:9222/devtools/page/x",
            f"ws://127.0.0.1.attacker.invalid:{srv.port}/x",
            "ws://10.1.2.3:9222/x",
            "ws://127.0.0.1:80/x",
            "https://127.0.0.1:9222/",
        ):
            out = self.run_cli("--cdp", url, "title")
            self.assertEqual(out.returncode, 2, url)
            self.assertIn("rejected", out.stderr)
        self.assertEqual(srv.requests, [])

    def test_external_cdp_in_environment_rejected(self):
        out = self.run_cli(
            "title", env={"AGENT_BROWSER_CDP": "ws://evil.example:9222/x"}
        )
        self.assertEqual(out.returncode, 2)

    def test_second_level_browser_returned_target_is_revalidated(self):
        """/json/list вернул чужой webSocketDebuggerUrl — он отбрасывается (двухуровневая проверка)."""
        evil = [
            {
                "type": "page",
                "webSocketDebuggerUrl": "ws://evil.example:9222/devtools/page/1",
            },
            {
                "type": "page",
                "webSocketDebuggerUrl": "ws://127.0.0.1.attacker.invalid:9222/x",
            },
            {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:80/x"},
            {"type": "page"},
            "junk",
        ]
        srv = self.cdp(targets=evil)
        out = self.run_cli("--cdp", f"http://127.0.0.1:{srv.port}", "title")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no loopback page target", out.stderr)
        self.assertEqual([r for r in srv.requests if r.startswith("WS")], [])

    def test_is_loopback_shared_with_bridge(self):
        self.assertIs(server.is_loopback_cdp_url, agent_browser.is_loopback_cdp_url)
        self.assertIs(
            server.discover_local_cdp_url, agent_browser.discover_local_cdp_url
        )
        for url in (
            "ws://127.0.0.1:9222/x",
            "http://[::1]:9222",
            "wss://localhost:2000",
        ):
            self.assertTrue(agent_browser.is_loopback_cdp_url(url), url)
        for url in (
            "ws://0.0.0.0:9222/",
            "ws://[::2]:9222/",
            "ws://127.0.0.1:1023/",
            "ws://a@127.0.0.1:9222/",
        ):
            self.assertFalse(agent_browser.is_loopback_cdp_url(url), url)


class TestSecondaryLoopbackDns(CliCase):
    """Вторичная проверка: имя хоста резолвится, все адреса loopback, соединение по IP."""

    @staticmethod
    def _infos(*addrs):
        out = []
        for a in addrs:
            if ":" in a:
                out.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (a, 0, 0, 0)))
            else:
                out.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)))
        return out

    def test_resolve_accepts_loopback_only(self):
        with mock.patch.object(
            socket,
            "getaddrinfo",
            return_value=self._infos("::1", "127.0.0.1", "127.0.0.1"),
        ):
            self.assertEqual(
                agent_browser.resolve_loopback_ips("localhost", 9222),
                ["::1", "127.0.0.1"],
            )

    def test_resolve_rejects_any_non_loopback_address(self):
        for addrs in (("10.1.2.3",), ("127.0.0.1", "93.184.216.34")):
            with mock.patch.object(
                socket, "getaddrinfo", return_value=self._infos(*addrs)
            ):
                with self.assertRaises(agent_browser.CdpError):
                    agent_browser.resolve_loopback_ips("localhost", 9222)

    def test_resolve_failure_is_cdp_error(self):
        with mock.patch.object(socket, "getaddrinfo", side_effect=socket.gaierror):
            with self.assertRaises(agent_browser.CdpError):
                agent_browser.resolve_loopback_ips("localhost", 9222)

    def test_poisoned_localhost_never_connects(self):
        with (
            mock.patch.object(
                socket, "getaddrinfo", return_value=self._infos("203.0.113.9")
            ),
            mock.patch.object(socket, "create_connection") as connect,
        ):
            with self.assertRaises(agent_browser.CdpError):
                agent_browser.WsClient("ws://localhost:9222/devtools/page/x", 1.0)
            base = agent_browser.urllib.parse.urlparse("http://localhost:9222")
            with self.assertRaises(agent_browser.CdpError):
                agent_browser._http_get_json(base, "/json/list", 1.0)
            connect.assert_not_called()

    def test_ws_and_http_connect_by_ip_and_fall_through_addresses(self):
        srv = self.cdp()
        seen = []
        real = socket.create_connection

        def spy(address, *a, **kw):
            seen.append(address[0])
            return real(address, *a, **kw)

        real_gai = socket.getaddrinfo
        infos = self._infos(
            "::1", "127.0.0.1"
        )  # слушает только 127.0.0.1: ::1 -> отказ -> следующий

        def fake_gai(host, *a, **kw):
            return infos if host == "localhost" else real_gai(host, *a, **kw)

        with (
            mock.patch.object(socket, "getaddrinfo", side_effect=fake_gai),
            mock.patch.object(socket, "create_connection", side_effect=spy),
        ):
            session = agent_browser.CdpSession(
                f"ws://localhost:{srv.port}/devtools/page/x", 5.0
            )
            session.close()
            base = agent_browser.urllib.parse.urlparse(f"http://localhost:{srv.port}")
            targets = agent_browser._http_get_json(base, "/json/list", 5.0)
        self.assertIsInstance(targets, list)
        self.assertEqual(seen, ["::1", "127.0.0.1", "::1", "127.0.0.1"])
        self.assertNotIn("localhost", seen)


class TestEnvLimits(unittest.TestCase):
    """Лимиты читаются при импорте: проверка в изолированном интерпретаторе."""

    def _limits(self, env):
        code = (
            "import sys; sys.path.insert(0, %r); import agent_browser as m; "
            "print(m.MAX_MESSAGE_BYTES, m.MAX_DISCOVERY_BYTES, m.PORT_MIN, m.PORT_MAX, "
            "int(m.is_loopback_cdp_url('http://127.0.0.1:9100')), "
            "int(m.is_loopback_cdp_url('http://127.0.0.1:8000')))" % str(ROOT / "tools")
        )
        full = {
            k: v for k, v in os.environ.items() if not k.startswith("AGENT_BROWSER_")
        }
        full.update(env)
        out = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            env=full,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return tuple(int(x) for x in out.stdout.split())

    def test_defaults(self):
        self.assertEqual(self._limits({})[:4], (64 << 20, 4096, 1024, 65535))

    def test_overrides_and_port_range_applies(self):
        got = self._limits(
            {
                "AGENT_BROWSER_MAX_MESSAGE_BYTES": "1000",
                "AGENT_BROWSER_MAX_DISCOVERY_BYTES": "128",
                "AGENT_BROWSER_PORT_MIN": "9000",
                "AGENT_BROWSER_PORT_MAX": "9300",
            }
        )
        self.assertEqual(got, (1000, 128, 9000, 9300, 1, 0))

    def test_garbage_and_inverted_range_fall_back(self):
        got = self._limits(
            {
                "AGENT_BROWSER_MAX_MESSAGE_BYTES": "abc",
                "AGENT_BROWSER_MAX_DISCOVERY_BYTES": "-5",
                "AGENT_BROWSER_PORT_MIN": "9300",
                "AGENT_BROWSER_PORT_MAX": "9000",
            }
        )
        self.assertEqual(got[:4], (64 << 20, 4096, 1024, 65535))


class TestAutonomousDiscovery(CliCase):
    def test_fallback_discovery_without_cdp_and_env(self):
        srv = self.cdp()
        disc = self.dir / "DevToolsActivePort"
        disc.write_text(f"{srv.port}\n/devtools/browser/aa-bb\n", encoding="utf-8")
        out = self.run_cli("title", env={"BRIDGE_CDP_DISCOVERY_PATH": str(disc)})
        self.assertEqual((out.returncode, out.stdout), (0, "Fake Title\n"), out.stderr)
        self.assertIn("/json/list", srv.requests)

    def test_discovery_port_only_file(self):
        srv = self.cdp()
        disc = self.dir / "devtools_port"
        disc.write_text(f"{srv.port}\n", encoding="utf-8")
        out = self.run_cli("title", env={"BRIDGE_CDP_DISCOVERY_PATH": str(disc)})
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_no_discovery_is_exit_2(self):
        out = self.run_cli("title")
        self.assertEqual(out.returncode, 2)
        self.assertIn("not found", out.stderr)

    def test_unsafe_discovery_files_are_ignored(self):
        disc = self.dir / "port"
        real = self.dir / "real"
        for content in ("80\n", "70000\n", "x\n", "9333\n" + "A" * 5000):
            disc.write_text(content, encoding="utf-8")
            with mock.patch.dict(os.environ, {"BRIDGE_CDP_DISCOVERY_PATH": str(disc)}):
                self.assertIsNone(agent_browser.discover_local_cdp_url(), content[:10])
        real.write_text("9333\n", encoding="utf-8")
        link = self.dir / "link"
        link.symlink_to(real)
        with mock.patch.dict(os.environ, {"BRIDGE_CDP_DISCOVERY_PATH": str(link)}):
            self.assertIsNone(agent_browser.discover_local_cdp_url())

    def test_discovery_default_paths(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("BRIDGE_CDP_DISCOVERY_PATH")
            paths = agent_browser._discovery_paths()
        self.assertTrue(paths[0].endswith("Antigravity/DevToolsActivePort"))
        self.assertTrue(paths[1].endswith(".config/agy-launch/devtools_port"))


class TestPackaging(unittest.TestCase):
    def test_wrapper_is_executable_and_runs_tool(self):
        wrapper = ROOT / "tools" / "agent-browser"
        self.assertTrue(os.access(wrapper, os.X_OK))
        text = wrapper.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env bash\n"))
        self.assertIn('exec python3 "$(dirname "$0")/agent_browser.py" "$@"', text)
        out = subprocess.run(
            [str(wrapper), "--help"], capture_output=True, text=True, timeout=30
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("navigate", out.stdout)

    def test_script_is_executable_stdlib_only(self):
        self.assertTrue(os.access(TOOL, os.X_OK))
        text = TOOL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env python3\n"))
        allowed = {
            "argparse",
            "base64",
            "hashlib",
            "http",
            "ipaddress",
            "json",
            "os",
            "re",
            "socket",
            "ssl",
            "stat",
            "struct",
            "sys",
            "time",
            "urllib",
            "__future__",
        }
        imported = {
            line.split()[1].split(".")[0]
            for line in text.splitlines()
            if line.startswith(("import ", "from "))
        }
        self.assertLessEqual(imported, allowed)


if __name__ == "__main__":
    unittest.main()

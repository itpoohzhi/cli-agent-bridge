#!/usr/bin/env python3
"""agent-browser: минимальный CLI к Chrome DevTools Protocol (CDP) на loopback.

Универсальный хелпер для любых CLI-агентов (ADR-0016): даёт штатному `bash` агента
управление авторизованной вкладкой браузера без плагинов и без внешних зависимостей
(только стандартная библиотека Python).

  agent-browser [--cdp URL] [--timeout S] eval "<expression>"
  agent-browser [--cdp URL] [--timeout S] title
  agent-browser [--cdp URL] [--timeout S] navigate "<url>"
  agent-browser [--cdp URL] [--timeout S] screenshot "<path.png>"

CDP-адрес: `--cdp`, иначе `$AGENT_BROWSER_CDP`, иначе локальный discovery
DevToolsActivePort (`$BRIDGE_CDP_DISCOVERY_PATH`, `~/Library/Application
Support/Antigravity/DevToolsActivePort`, `~/.config/agy-launch/devtools_port`).

Безопасность: допускаются только loopback-адреса (`ws|wss|http` на 127.0.0.1,
localhost, ::1, порт $AGENT_BROWSER_PORT_MIN..$AGENT_BROWSER_PORT_MAX, по умолчанию 1024..65535);
имя хоста дополнительно резолвится, все адреса обязаны быть loopback, подключение — по IP. Проверка двухуровневая: адрес из аргумента/окружения
и адрес вкладки, который вернул браузер (`webSocketDebuggerUrl`). Полный WebSocket URL
(в нём токен сессии браузера) в вывод и ошибки не попадает.

Коды выхода: 0 — успех, 1 — ошибка выполнения (CDP/сеть/таймаут), 2 — ошибка аргументов.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import stat
import struct
import sys
import time
import urllib.parse


def _env_int(name: str, default: int, low: int = 1, high: int = 1 << 40) -> int:
    """Целочисленная настройка из окружения; нечисло или значение вне [low, high] -> дефолт."""
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if low <= value <= high else default


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
PORT_MIN = _env_int("AGENT_BROWSER_PORT_MIN", 1024, 1, 65535)
PORT_MAX = _env_int("AGENT_BROWSER_PORT_MAX", 65535, 1, 65535)
if PORT_MIN > PORT_MAX:
    PORT_MIN, PORT_MAX = 1024, 65535
CDP_SCHEMES = frozenset({"ws", "wss", "http"})
DEFAULT_TIMEOUT_S = 5.0
# скриншот большой вкладки в base64
MAX_MESSAGE_BYTES = _env_int("AGENT_BROWSER_MAX_MESSAGE_BYTES", 64 << 20)
MAX_DISCOVERY_BYTES = _env_int("AGENT_BROWSER_MAX_DISCOVERY_BYTES", 4096)
_WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_BROWSER_PATH = re.compile(r"/devtools/browser/[A-Za-z0-9._-]{1,128}")
_NAVIGATE_SCHEMES = frozenset({"http", "https", "about"})
_URL_MASK = re.compile(r"(?:wss?|https?)://\S+", re.IGNORECASE)


class CdpError(Exception):
    """Ошибка выполнения команды CDP (сеть, протокол, таймаут, исключение страницы)."""


class UsageError(Exception):
    """Ошибка аргументов/окружения (код выхода 2)."""


def mask_urls(text: str) -> str:
    """Скрыть URL в диагностике: путь `/devtools/browser/<id>` — секрет сессии."""
    return _URL_MASK.sub("<url>", text)


def is_loopback_cdp_url(url: object) -> bool:
    """Строгая проверка CDP-адреса: схема ws|wss|http, хост ровно loopback, порт 1024..65535."""
    if not isinstance(url, str) or not url or url != url.strip():
        return False
    if any(ord(ch) < 0x21 or ord(ch) == 0x7F for ch in url):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme not in CDP_SCHEMES:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.hostname not in LOOPBACK_HOSTS:
        return False
    return port is not None and PORT_MIN <= port <= PORT_MAX


def resolve_loopback_ips(host: str, port: int) -> list[str]:
    """Вторичная проверка: ВСЕ адреса хоста — loopback; возвращает IP для подключения по ним.

    Защита от подмены имени (`localhost` -> чужой адрес через hosts/DNS): соединение идёт по IP,
    а не по имени, и только если ни один из резолвленных адресов не вне loopback.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise CdpError("loopback host resolution failed") from None
    addrs: list[str] = []
    for info in infos:
        addr = str(info[4][0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise CdpError("host resolved to a non-IP address") from None
        if not ip.is_loopback:
            raise CdpError("host resolves to a non-loopback address")
        if addr not in addrs:
            addrs.append(addr)
    if not addrs:
        raise CdpError("loopback host resolution failed")
    return addrs


def connect_loopback(host: str, port: int, timeout: float) -> socket.socket:
    """TCP-соединение с loopback-хостом по проверенным IP (по очереди: ::1 и 127.0.0.1)."""
    last: OSError | None = None
    for addr in resolve_loopback_ips(host, port):
        try:
            return socket.create_connection((addr, port), timeout=timeout)
        except OSError as exc:
            last = exc
    raise last or OSError("connect failed")


def _discovery_paths() -> list[str]:
    override = os.environ.get("BRIDGE_CDP_DISCOVERY_PATH")
    if override:
        return [os.path.expanduser(override)]
    return [
        os.path.expanduser(
            "~/Library/Application Support/Antigravity/DevToolsActivePort"
        ),
        os.path.expanduser("~/.config/agy-launch/devtools_port"),
    ]


def _read_discovery_file(path: str) -> str | None:
    """Loopback CDP-адрес из файла DevToolsActivePort (строка 1 — порт, строка 2 — путь) либо None."""
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid():
            return None
        if st.st_size > MAX_DISCOVERY_BYTES:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read(MAX_DISCOVERY_BYTES).splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not lines or not re.fullmatch(r"[0-9]{1,5}", lines[0].strip()):
        return None
    port = int(lines[0].strip())
    if not PORT_MIN <= port <= PORT_MAX:
        return None
    ws_path = lines[1].strip() if len(lines) > 1 else ""
    if ws_path and _BROWSER_PATH.fullmatch(ws_path):
        url = f"ws://127.0.0.1:{port}{ws_path}"
    else:
        url = f"http://127.0.0.1:{port}"
    return url if is_loopback_cdp_url(url) else None


def discover_local_cdp_url() -> str | None:
    """Безопасный discovery локального DevTools-порта на loopback; None — не найден/не прошёл проверку."""
    for path in _discovery_paths():
        url = _read_discovery_file(path)
        if url:
            return url
    return None


def resolve_cdp(explicit: str | None) -> str:
    """CDP-адрес: --cdp, затем $AGENT_BROWSER_CDP, затем discovery; всегда через is_loopback_cdp_url."""
    candidate = explicit or os.environ.get("AGENT_BROWSER_CDP") or ""
    if candidate:
        if not is_loopback_cdp_url(candidate):
            raise UsageError(
                "CDP address rejected: only loopback ws|wss|http on 127.0.0.1, "
                "localhost or ::1 with port 1024..65535 is allowed"
            )
        return candidate
    found = discover_local_cdp_url()
    if found is None:
        raise UsageError(
            "CDP address not found: pass --cdp, set AGENT_BROWSER_CDP or start a "
            "browser with DevToolsActivePort"
        )
    return found


class WsClient:
    """Минимальный клиент WebSocket (RFC 6455) для CDP: текстовые кадры, маска клиента."""

    def __init__(self, url: str, timeout: float):
        if not is_loopback_cdp_url(url) or not url.startswith(("ws://", "wss://")):
            raise CdpError("websocket target is not a loopback ws address")
        parsed = urllib.parse.urlparse(url)
        host, port = parsed.hostname or "127.0.0.1", parsed.port or 0
        self._deadline = time.monotonic() + timeout
        self._timeout = timeout
        try:
            raw = connect_loopback(host, port, timeout)
            if parsed.scheme == "wss":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE  # loopback: сертификат самоподписанный
                raw = ctx.wrap_socket(raw, server_hostname=host)
            self.sock = raw
        except (OSError, ssl.SSLError) as exc:
            raise CdpError(f"connect failed: {mask_urls(str(exc))}") from None
        self._buf = b""
        try:
            self._handshake(parsed)
        except BaseException:
            self.close()
            raise

    def _remaining(self) -> float:
        left = self._deadline - time.monotonic()
        if left <= 0:
            raise CdpError("timeout")
        return left

    def _handshake(self, parsed: urllib.parse.ParseResult) -> None:
        key = base64.b64encode(os.urandom(16))
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        host = (
            f"[{parsed.hostname}]"
            if ":" in (parsed.hostname or "")
            else parsed.hostname
        )
        request = (
            f"GET {target} HTTP/1.1\r\nHost: {host}:{parsed.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key.decode()}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        try:
            self.sock.settimeout(self._remaining())
            self.sock.sendall(request.encode("ascii"))
            while b"\r\n\r\n" not in self._buf:
                if len(self._buf) > 65536:
                    raise CdpError("handshake response too large")
                self.sock.settimeout(self._remaining())
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise CdpError("handshake: connection closed")
                self._buf += chunk
        except (OSError, UnicodeEncodeError) as exc:
            raise CdpError(f"handshake failed: {mask_urls(str(exc))}") from None
        head, _, self._buf = self._buf.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        if len(lines) < 1 or " 101 " not in lines[0] + " ":
            raise CdpError(f"handshake rejected: {lines[0][:60]!r}")
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        accept = base64.b64encode(hashlib.sha1(key + _WS_GUID).digest()).decode()
        if headers.get("sec-websocket-accept") != accept:
            raise CdpError("handshake: bad Sec-WebSocket-Accept")

    def _recv_exact(self, count: int) -> bytes:
        while len(self._buf) < count:
            self.sock.settimeout(self._remaining())
            try:
                chunk = self.sock.recv(65536)
            except (socket.timeout, TimeoutError):
                raise CdpError("timeout") from None
            except OSError as exc:
                raise CdpError(f"recv failed: {mask_urls(str(exc))}") from None
            if not chunk:
                raise CdpError("connection closed")
            self._buf += chunk
        data, self._buf = self._buf[:count], self._buf[count:]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        header = bytes([0x80 | opcode])
        size = len(payload)
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 1 << 16:
            header += bytes([0x80 | 126]) + struct.pack(">H", size)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", size)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        try:
            self.sock.settimeout(self._remaining())
            self.sock.sendall(header + mask + masked)
        except (socket.timeout, TimeoutError):
            raise CdpError("timeout") from None
        except OSError as exc:
            raise CdpError(f"send failed: {mask_urls(str(exc))}") from None

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def recv_text(self) -> str:
        message = bytearray()
        while True:
            b1, b2 = self._recv_exact(2)
            fin, opcode = b1 & 0x80, b1 & 0x0F
            size = b2 & 0x7F
            if size == 126:
                (size,) = struct.unpack(">H", self._recv_exact(2))
            elif size == 127:
                (size,) = struct.unpack(">Q", self._recv_exact(8))
            if size > MAX_MESSAGE_BYTES:
                raise CdpError("message too large")
            mask = self._recv_exact(4) if b2 & 0x80 else b""
            payload = self._recv_exact(size)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise CdpError("connection closed by peer")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            message += payload
            if len(message) > MAX_MESSAGE_BYTES:
                raise CdpError("message too large")
            if fin:
                return message.decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class CdpSession:
    """Вкладка браузера: JSON-RPC поверх WebSocket, события копятся до явного ожидания."""

    def __init__(self, ws_url: str, timeout: float):
        self.timeout = timeout
        self.ws = WsClient(ws_url, timeout)
        self._next_id = 0
        self.events: list[dict] = []

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        call_id = self._next_id
        self.ws.send_text(
            json.dumps({"id": call_id, "method": method, "params": params or {}})
        )
        while True:
            try:
                msg = json.loads(self.ws.recv_text())
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("id") == call_id:
                if "error" in msg:
                    err = msg["error"] if isinstance(msg["error"], dict) else {}
                    raise CdpError(f"{method}: {err.get('message', 'error')}"[:300])
                result = msg.get("result")
                return result if isinstance(result, dict) else {}
            if "method" in msg:
                self.events.append(msg)

    def wait_event(self, name: str) -> bool:
        if any(e.get("method") == name for e in self.events):
            return True
        while True:
            try:
                msg = json.loads(self.ws.recv_text())
            except ValueError:
                continue
            except CdpError:
                return False
            if isinstance(msg, dict) and msg.get("method") == name:
                return True

    def close(self) -> None:
        self.ws.close()


def _http_get_json(base: urllib.parse.ParseResult, path: str, timeout: float):
    host = base.hostname or "127.0.0.1"
    conn = http.client.HTTPConnection(host, base.port, timeout=timeout)
    try:
        conn.sock = connect_loopback(
            host, base.port or 0, timeout
        )  # по проверенному IP, не по имени
        conn.request("GET", path, headers={"Host": f"127.0.0.1:{base.port}"})
        resp = conn.getresponse()
        body = resp.read(MAX_MESSAGE_BYTES)
        if resp.status != 200:
            raise CdpError(f"{path}: HTTP {resp.status}")
        return json.loads(body.decode("utf-8", "replace"))
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise CdpError(f"{path}: {mask_urls(str(exc))}") from None
    finally:
        conn.close()


def resolve_page_ws(cdp: str, timeout: float) -> str:
    """WebSocket URL вкладки: page-адрес берётся как есть, иначе первая вкладка из /json/list.

    Второй уровень loopback-проверки: `webSocketDebuggerUrl` приходит от браузера и
    повторно проходит is_loopback_cdp_url (чужой хост/порт отбрасывается).
    """
    parsed = urllib.parse.urlparse(cdp)
    if parsed.scheme in ("ws", "wss") and parsed.path.startswith("/devtools/page/"):
        return cdp
    base = urllib.parse.urlparse(f"http://{parsed.netloc}")
    targets = _http_get_json(base, "/json/list", timeout)
    if not isinstance(targets, list):
        raise CdpError("unexpected /json/list response")
    for target in targets:
        if not isinstance(target, dict) or target.get("type") != "page":
            continue
        ws_url = target.get("webSocketDebuggerUrl")
        if isinstance(ws_url, str) and is_loopback_cdp_url(ws_url):
            return ws_url
    raise CdpError("no loopback page target found")


def cmd_eval(session: CdpSession, expression: str) -> str:
    result = session.call(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
    )
    if "exceptionDetails" in result:
        details = result["exceptionDetails"]
        text = (
            (details.get("exception") or {}).get("description")
            or details.get("text")
            or "exception"
        )
        raise CdpError(f"eval exception: {str(text)[:300]}")
    remote = result.get("result") or {}
    if "value" in remote:
        value = remote["value"]
        return (
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        )
    return str(remote.get("description") or remote.get("type") or "undefined")


def cmd_title(session: CdpSession) -> str:
    return cmd_eval(session, "document.title")


def cmd_navigate(session: CdpSession, url: str) -> str:
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in _NAVIGATE_SCHEMES:
        raise UsageError(f"navigate: scheme {scheme!r} is not allowed")
    session.call("Page.enable")
    result = session.call("Page.navigate", {"url": url})
    if result.get("errorText"):
        raise CdpError(f"navigate: {result['errorText']}")
    if not session.wait_event("Page.loadEventFired"):
        raise CdpError("navigate: page load not confirmed (timeout or connection lost)")
    return url


def cmd_screenshot(session: CdpSession, path: str) -> str:
    result = session.call("Page.captureScreenshot", {"format": "png"})
    data = result.get("data")
    if not isinstance(data, str) or not data:
        raise CdpError("screenshot: empty data")
    try:
        raw = base64.b64decode(data, validate=True)
    except ValueError:
        raise CdpError("screenshot: invalid base64") from None
    target = os.path.abspath(os.path.expanduser(path))
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        # O_CREAT применяет 0o600 только к новому файлу: у существующего (0644) права ужимаем до записи.
        os.fchmod(handle.fileno(), 0o600)
        handle.write(raw)
    return target


def _timeout_default() -> float:
    try:
        value = float(os.environ.get("BRIDGE_CDP_TIMEOUT_S", DEFAULT_TIMEOUT_S))
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else DEFAULT_TIMEOUT_S


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-browser",
        description="Минимальный CLI к Chrome DevTools Protocol на loopback (ADR-0016).",
    )
    parser.add_argument(
        "--cdp",
        metavar="URL",
        help="loopback CDP-адрес (ws|wss|http); по умолчанию $AGENT_BROWSER_CDP или discovery",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="S",
        help="таймаут операции в секундах (по умолчанию $BRIDGE_CDP_TIMEOUT_S или 5.0)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("eval", help="выполнить JS-выражение").add_argument("expression")
    sub.add_parser("title", help="заголовок страницы")
    sub.add_parser("navigate", help="открыть URL").add_argument("url")
    sub.add_parser("screenshot", help="PNG-скриншот в файл").add_argument("path")
    return parser


def run(argv: list[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help -> 0, ошибка аргументов -> 2
        return int(exc.code) if isinstance(exc.code, int) else 2
    timeout = args.timeout if args.timeout and args.timeout > 0 else _timeout_default()
    session: CdpSession | None = None
    try:
        cdp = resolve_cdp(args.cdp)
        session = CdpSession(resolve_page_ws(cdp, timeout), timeout)
        if args.command == "eval":
            out = cmd_eval(session, args.expression)
        elif args.command == "title":
            out = cmd_title(session)
        elif args.command == "navigate":
            out = cmd_navigate(session, args.url)
        else:
            out = cmd_screenshot(session, args.path)
    except UsageError as exc:
        sys.stderr.write(f"agent-browser: {exc}\n")
        return 2
    except CdpError as exc:
        sys.stderr.write(f"agent-browser: {mask_urls(str(exc))}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"agent-browser: {mask_urls(str(exc))}\n")
        return 1
    finally:
        if session is not None:
            session.close()
    sys.stdout.write(out + "\n")
    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()

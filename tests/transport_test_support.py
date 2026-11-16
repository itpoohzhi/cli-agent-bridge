"""Изолированные wire-фикстуры и типизированные семантические расхождения W0."""

from __future__ import annotations

import ast
import http.client
import os
import re
import subprocess
from functools import cache
from pathlib import Path
import json
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import pytest

from tests.transport_wire_support import (
    RecordingUpstream as RecordingUpstream,
    RunningHTTPServer as RunningHTTPServer,
    WireRequest as WireRequest,
    WireSettings as WireSettings,
)

CANON = Path.home() / "Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md"
TRANSPORT_IMPORTS = frozenset(
    {
        "fastapi",
        "litestar",
        "starlette",
        "flask",
        "aiohttp.web",
        "websockets",
        "typer",
        "click",
    }
)
PERSISTENCE_IMPORTS = frozenset(
    {"sqlalchemy", "asyncpg", "psycopg", "sqlite3", "redis", "valkey", "aioboto3"}
)
NET_PROC_IO_IMPORTS = frozenset(
    {"httpx", "aiohttp", "requests", "urllib", "curl_cffi", "subprocess", "socket"}
)


@cache
def canonical_prefixes(canon: Path) -> tuple[tuple[str, str], ...]:
    """Замороженный канон работает в CI; локальный оригинал проверяет drift."""
    groups = {
        "TRANSPORT_IMPORTS": TRANSPORT_IMPORTS,
        "PERSISTENCE_IMPORTS": PERSISTENCE_IMPORTS,
        "NET_PROC_IO_IMPORTS": NET_PROC_IO_IMPORTS,
    }
    if canon.is_file():
        tables = re.findall(
            r"`((?:TRANSPORT|PERSISTENCE|NET_PROC_IO)_IMPORTS) = (\{[^`]+\})`",
            canon.read_text(),
        )
        assert len(tables) == 3
        assert {
            name: frozenset(ast.literal_eval(value)) for name, value in tables
        } == groups
    return tuple((prefix, name) for name, values in groups.items() for prefix in values)


def categories(targets: frozenset[str]) -> frozenset[str]:
    """Longest-prefix не смешивает aiohttp.web и сетевой aiohttp."""
    found = set()
    for target in targets:
        matches = [
            (prefix, name)
            for prefix, name in canonical_prefixes(CANON)
            if target == prefix or target.startswith(prefix + ".")
        ]
        if matches:
            found.add(max(matches, key=lambda pair: len(pair[0]))[1])
    return frozenset(found)


def require_base(root: Path, base: str) -> None:
    """Пропускает только проверки, требующие отсутствующего Git-объекта."""
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{base}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("base commit unavailable in shallow clone")


def require_wave_artifacts(run: Path) -> None:
    """Артефакты волн не являются обязательной частью чистого checkout."""
    names = ("architecture-packet.json", "baseline-monoliths.json")
    if not all((run / "architecture" / name).is_file() for name in names):
        pytest.skip("wave run artifacts absent in clean checkout")


def wave_changes(
    root: Path, run: Path, base: str, changed: frozenset[str]
) -> frozenset[str]:
    """Ограничивает scope волны её аттестацией, не будущими коммитами dev."""
    for name in ("final-results.json", "trusted-inputs.json"):
        path = run / "qa" / name
        if not path.is_file():
            continue
        report = json.loads(path.read_bytes())
        head = report.get("wave_head_sha") or report.get("head_sha")
        if not head:
            continue
        ancestor = subprocess.run(
            ["git", "-C", str(root), "merge-base", head, "HEAD"],
            capture_output=True,
            check=False,
        )
        if ancestor.returncode == 0:
            boundary = ancestor.stdout.decode().strip()
            output = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(root),
                    "diff",
                    "--name-only",
                    "-z",
                    f"{base}..{boundary}",
                ]
            )
            return frozenset(os.fsdecode(p) for p in output.split(b"\0") if p)
    return changed


class SemanticFailure(AssertionError):
    """Только расхождение результата, не ошибка импорта, настройки или транспорта."""

    def __init__(self, defect: str, actual: object, expected: object) -> None:
        self.defect, self.actual, self.expected = defect, actual, expected
        super().__init__(defect)


def semantic_equal(actual: object, expected: object, defect: str) -> None:
    """Сравнивает наблюдаемый результат с независимо заданным ожиданием."""
    if not defect:
        raise ValueError("Не задан идентификатор семантического дефекта")
    if actual != expected:
        raise SemanticFailure(defect, actual, expected)


class RecordingSink:
    """Наблюдает commit заголовков и каждого downstream chunk."""

    accepts_presend_errors = False

    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: tuple[tuple[str, str], ...] = ()
        self.chunks: list[bytes] = []
        self.gone = False

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        if self.status is not None:
            raise AssertionError("Повторный commit заголовков")
        self.status, self.headers = status, tuple(headers)

    def write(self, body: bytes) -> None:
        if self.status is None:
            raise AssertionError("Тело отправлено до заголовков")
        self.chunks.append(body)

    @property
    def body(self) -> bytes:
        return b"".join(self.chunks)

    def client_gone(self) -> bool:
        return self.gone

    def error_type(self) -> str:
        return ""


def make_adapter(
    upstream: RecordingUpstream, config: Mapping[str, Any] | None = None
) -> Any:
    """Создаёт настоящий адаптер только на локальную recording-границу."""
    from adapters.passthrough_adapter import PassthroughAdapter

    resolved = {
        "kind": "passthrough",
        "base_url": upstream.base_url,
        "max_concurrent": 1,
    }
    resolved.update(config or {})
    return PassthroughAdapter("recording", resolved, lambda: {})


def wire_post(
    port: int,
    payload: Mapping[str, object],
    headers: Mapping[str, str] | None = None,
    settings: WireSettings | None = None,
) -> tuple[int, bytes]:
    """Входит в настоящий HTTP Handler, без подмены do_POST/dispatch."""
    options = settings or WireSettings()
    connection = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=options.timeout_s
    )
    try:
        connection.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(dict(payload)).encode(),
            dict(headers or {}),
        )
        response = connection.getresponse()
        return response.status, response.read(options.max_body_bytes + 1)
    finally:
        connection.close()


@pytest.mark.parametrize(
    "failure", ["semantic", "wrong_name", "assert", "import", "setup"]
)
def test_report_hook_requires_exact_semantic_exception(failure: str) -> None:
    from tests import transport_red_oracle as oracle, transport_test_support as support

    errors = {
        "semantic": support.SemanticFailure("known", 2, 1),
        "wrong_name": support.SemanticFailure("other", 2, 1),
        "assert": AssertionError("known"),
        "import": ImportError("known"),
        "setup": support.SemanticFailure("known", 2, 1),
    }
    plugin = oracle.RedReports()
    item = SimpleNamespace(
        nodeid="exact", get_closest_marker=lambda _: SimpleNamespace(args=("known",))
    )
    call = SimpleNamespace(
        when="setup" if failure == "setup" else "call",
        excinfo=SimpleNamespace(value=errors[failure]),
    )
    hook = plugin.pytest_runtest_makereport(item, call)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(SimpleNamespace(get_result=lambda: SimpleNamespace(outcome="failed")))
    assert plugin.reports[0]["semantic"] is (failure == "semantic")

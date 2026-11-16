"""W0: принимает только именованное семантическое падение точного baseline.

Контракт тестов: @pytest.mark.semantic_red("defect_id") и
semantic_equal(actual, expected, "defect_id"). Любой обычный assert/exception,
skip, xfail, ошибка collection/setup/teardown или авария процесса закрывает gate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "TRANSPORT_RED_REPORT="
FILES = {
    "W0-A": ("test_transport_routing.py", "test_routing_catalog.py"),
    "W0-B": ("test_transport_eligibility.py", "test_transport_replay.py"),
    "W0-C": ("test_transport_headers.py", "test_transport_compatibility.py"),
    "W0-D": ("transport_red_oracle.py",),
    "W0-E": ("test_transport_modularity.py", "test_transport_isolation.py"),
    "W0-F": ("test_transport_resilience.py", "test_dead_provider_keys.py"),
}
BOOTSTRAP = "test_semantic_bootstrap_502_no_replay"


class RedReports:
    """Получает тип исключения из pytest, а не ищет слова в traceback."""

    def __init__(self) -> None:
        self.nodes: list[str] = []
        self.reports: list[dict[str, object]] = []
        self.collection_errors = 0

    def pytest_configure(self, config: pytest.Config) -> None:
        config.addinivalue_line("markers", "semantic_red(defect): ожидаемый дефект W0")

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.nodes = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report: Any) -> None:
        self.collection_errors += int(report.failed)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: Any) -> Any:
        from tests.transport_test_support import SemanticFailure

        outcome = yield
        report = outcome.get_result()
        marker = item.get_closest_marker("semantic_red")
        defect = marker.args[0] if marker and len(marker.args) == 1 else None
        error = call.excinfo.value if call.excinfo is not None else None
        semantic = (
            call.when == "call"
            and type(error) is SemanticFailure
            and isinstance(defect, str)
            and error.defect == defect
            and error.actual != error.expected
        )
        self.reports.append(
            {
                "node": item.nodeid,
                "when": call.when,
                "outcome": report.outcome,
                "semantic": semantic,
                "defect": defect if semantic else None,
                "xfail": hasattr(report, "wasxfail"),
            }
        )

    def payload(self) -> dict[str, object]:
        return {
            "nodes": self.nodes,
            "reports": self.reports,
            "collection_errors": self.collection_errors,
        }


def _phase_red(phases: list[dict[str, Any]]) -> int:
    if [report["when"] for report in phases] != ["setup", "call", "teardown"]:
        return -1
    if any(report["xfail"] for report in phases):
        return -1
    if [phases[index]["outcome"] for index in (0, 2)] != ["passed", "passed"]:
        return -1
    call = phases[1]
    if call["outcome"] == "passed":
        return 0
    return 1 if call["outcome"] == "failed" and call["semantic"] else -1


def semantic_red_ok(payload: dict[str, Any], returncode: int) -> bool:
    """Требует полный цикл каждой выбранной ноды и только semantic call failures."""
    nodes = payload.get("nodes", [])
    if returncode != 1 or not nodes or payload.get("collection_errors") != 0:
        return False
    reports = payload.get("reports", [])
    if len(reports) != 3 * len(nodes) or len(set(nodes)) != len(nodes):
        return False
    results = [_phase_red([r for r in reports if r["node"] == node]) for node in nodes]
    return min(results) >= 0 and max(results) == 1


def _git(*arguments: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Недоступен git")
    return subprocess.run(
        [git, "-C", str(ROOT), *arguments],
        capture_output=True,
        text=True,
        check=True,
        timeout=float(os.environ.get("TRANSPORT_RED_GIT_TIMEOUT_S", "10")),
    ).stdout.strip()


def _baseline(base: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", base) is None:
        raise ValueError("Требуется полный SHA baseline")
    if _git("rev-parse", "HEAD") != base:
        raise ValueError("HEAD не совпадает с заданным baseline")
    _git("diff", "--quiet", base, "--", ".", ":(exclude)tests", ":(exclude).ai-team")
    for mode in ("--exclude-standard", "--ignored"):
        paths = _git("ls-files", "--others", mode, "--exclude-standard", "--", "core", "adapters")
        if any(path.endswith(".py") for path in paths.splitlines()):
            raise ValueError("Неотслеживаемый runtime Python не принадлежит baseline")


def _probe(card: str) -> int:
    plugin = RedReports()
    paths = [str(ROOT / "tests" / name) for name in FILES[card]]
    if card == "W0-D":
        paths = [paths[0] + "::" + BOOTSTRAP]
    result = int(pytest.main(["-p", "no:cacheprovider", "-q", *paths], plugins=[plugin]))
    print(PREFIX + json.dumps(plugin.payload(), sort_keys=True))
    return result


def _run(card: str, timeout_s: float) -> tuple[int, dict[str, Any]]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["TRANSPORT_RED_PROBE"] = "1"
    environment.pop("PYTEST_ADDOPTS", None)
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--probe",
            "--card",
            card,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    lines = [line[len(PREFIX) :] for line in child.stdout.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        raise RuntimeError(f"Нет единственного отчёта pytest, rc={child.returncode}")
    return child.returncode, json.loads(lines[0])


def _verified_defects(card: str, code: int, payload: dict[str, Any]) -> list[str]:
    if not semantic_red_ok(payload, code):
        raise RuntimeError(f"Не подтверждён semantic red, pytest rc={code}")
    covered = {node.split("::")[0].split("/")[-1] for node in payload["nodes"]}
    if covered != set(FILES[card]):
        raise RuntimeError("Неполная поверхность карточки")
    return [r["defect"] for r in payload["reports"] if r["semantic"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--card", required=True, choices=tuple(FILES))
    parser.add_argument("--require-semantic-red", action="store_true")
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=float(os.environ.get("TRANSPORT_RED_TIMEOUT_S", "60")),
    )
    args = parser.parse_args()
    if args.probe:
        return _probe(args.card)
    try:
        if not args.require_semantic_red or not args.base or args.timeout_s <= 0:
            raise ValueError("Нужны --base, --require-semantic-red и положительный timeout")
        _baseline(args.base)
        code, payload = _run(args.card, args.timeout_s)
        defects = _verified_defects(args.card, code, payload)
        print(json.dumps({"card": args.card, "base": args.base, "semantic_red": defects}))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"BLOCKED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


@pytest.mark.semantic_red("unsafe_502_replay")
@pytest.mark.skipif(os.environ.get("TRANSPORT_RED_PROBE") != "1", reason="W0 baseline probe")
@pytest.mark.parametrize("stream", [False, True])
def test_semantic_bootstrap_502_no_replay(monkeypatch: pytest.MonkeyPatch, stream: bool) -> None:
    from tests.transport_test_support import (
        RecordingSink,
        RecordingUpstream,
        make_adapter,
        semantic_equal,
    )

    monkeypatch.setenv("BRIDGE_PASSTHROUGH_PRESEND_MAX_RETRIES", "1")
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_PRESEND_RETRY_DELAY_S", "0.001")
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_PRESEND_RETRY_MAX_DELAY_S", "0.001")
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "false")
    monkeypatch.setenv("BRIDGE_CONNECTION_POOLING_ENABLED", "false")
    request = {"model": "m", "stream": stream}
    raw = json.dumps(request).encode()
    with RecordingUpstream() as upstream:
        upstream.respond = lambda handler, body: upstream.json(
            handler, {"error": {"retryable": True, "type": "proxy_connect_failed"}}, 502
        )
        adapter, sink = make_adapter(upstream), RecordingSink()
        try:
            adapter.handle(
                path="/v1/chat/completions",
                raw_body=raw,
                request=request,
                headers={},
                sink=sink,
            )
        finally:
            adapter.shutdown()
        assert sink.status == 502
        assert upstream.post_count in (1, 2)
        assert all(record.body == raw for record in upstream.requests)
        actual = (upstream.post_count, upstream.body_bytes)
    semantic_equal(actual, (1, len(raw)), "unsafe_502_replay")


def _sample_report() -> dict[str, Any]:
    phases = [
        {
            "node": "exact",
            "when": when,
            "outcome": outcome,
            "semantic": semantic,
            "defect": "known" if semantic else None,
            "xfail": False,
        }
        for when, outcome, semantic in (
            ("setup", "passed", False),
            ("call", "failed", True),
            ("teardown", "passed", False),
        )
    ]
    return {"nodes": ["exact"], "reports": phases, "collection_errors": 0}


@pytest.mark.parametrize("code", [-11, -6, 0, 2, 3, 4, 5, 134, 139])
def test_oracle_rejects_nonsemantic_process_exit(code: int) -> None:
    assert not semantic_red_ok(_sample_report(), code)


@pytest.mark.parametrize("phase", [0, 1, 2])
@pytest.mark.parametrize("outcome", ["failed", "skipped"])
def test_oracle_rejects_infrastructure_or_skip(phase: int, outcome: str) -> None:
    payload = _sample_report()
    payload["reports"][phase]["outcome"] = outcome
    payload["reports"][phase]["semantic"] = False
    assert not semantic_red_ok(payload, 1)


def test_oracle_requires_collection_and_all_phases() -> None:
    payload = _sample_report()
    assert semantic_red_ok(payload, 1)
    payload["collection_errors"] = 1
    assert not semantic_red_ok(payload, 1)
    payload["collection_errors"] = 0
    payload["reports"].pop()
    assert not semantic_red_ok(payload, 1)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())

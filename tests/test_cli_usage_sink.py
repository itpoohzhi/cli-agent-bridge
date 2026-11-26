"""Тесты единого CLI-sink: kill-switch, конкурентность, ротация, безопасность, fail-open, парсер и эмиттер."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from core.cli_usage_sink import (
    CLI_USAGE_ALLOWLIST,
    ENABLED_ENV,
    MAX_SINK_LINE_BYTES,
    CliSinkConfig,
    CliUsageSink,
    parse_cli_usage_payload,
)

_ROOT = Path(__file__).resolve().parent.parent
_EMIT = _ROOT / "scripts" / "cli_usage_emit.py"
_WORKER = (
    "import sys\n"
    "from core.cli_usage_sink import CliSinkConfig, CliUsageSink\n"
    "path, worker = sys.argv[1], sys.argv[2]\n"
    "sink = CliUsageSink(path, CliSinkConfig(max_bytes=2048, max_archives=50))\n"
    "ok = sum(sink.write({'request_id': f'{worker}-{i}', 'model': 'm', 'prompt_tokens': i}) for i in range(40))\n"
    "sys.exit(0 if ok == 40 else 1)\n"
)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENABLED_ENV, "1")


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _all_records(base: Path) -> list[dict[str, Any]]:
    files = [p for p in base.parent.iterdir() if p.name.startswith(base.name) and not p.name.endswith(".lock")]
    return [json.loads(line) for p in files for line in _lines(p)]


# --- 1. kill-switch -------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "0", "", "no", "off", "false", "2"])
def test_kill_switch_off_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(ENABLED_ENV, raising=False)
    else:
        monkeypatch.setenv(ENABLED_ENV, value)
    target = tmp_path / "t" / "cli-usage.jsonl"
    assert CliUsageSink(str(target)).write({"model": "m"}) is False
    assert not target.parent.exists()


@pytest.mark.parametrize("value", ["1", "true", "YES", "On"])
def test_kill_switch_on_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(ENABLED_ENV, value)
    target = tmp_path / "cli-usage.jsonl"
    assert CliUsageSink(str(target)).write({"model": "m", "prompt_tokens": 3}) is True
    rec = json.loads(_lines(target)[0])
    assert rec["model"] == "m" and rec["prompt_tokens"] == 3 and "ts" in rec


def test_path_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: None) -> None:
    target = tmp_path / "env.jsonl"
    monkeypatch.setenv("BRIDGE_CLI_USAGE_LOG_PATH", str(target))
    assert CliUsageSink().write({"model": "m"}) is True
    assert target.exists()


# --- 2. конкурентность (THREAT-002) ---------------------------------------------------------------------


def test_concurrent_processes_no_lost_or_torn_lines(tmp_path: Path) -> None:
    target = tmp_path / "cli-usage.jsonl"
    env = {**os.environ, ENABLED_ENV: "1", "PYTHONPATH": str(_ROOT)}
    procs = [
        subprocess.Popen([sys.executable, "-c", _WORKER, str(target), f"w{n}"], env=env, cwd=_ROOT)
        for n in range(6)
    ]
    assert [p.wait(timeout=120) for p in procs] == [0] * 6
    records = _all_records(target)
    ids = {r["request_id"] for r in records}
    assert len(records) == 240 and len(ids) == 240
    assert (tmp_path / "cli-usage.jsonl.1").exists()  # ротация реально происходила


# --- 3. ротация -----------------------------------------------------------------------------------------


def test_rotation_overflow_keeps_max_archives(tmp_path: Path, enabled: None) -> None:
    target = tmp_path / "cli-usage.jsonl"
    sink = CliUsageSink(str(target), CliSinkConfig(max_bytes=300, max_archives=2))
    results = [sink.write({"request_id": f"r{i}", "model": "model-x"}) for i in range(30)]
    assert all(results)
    names = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("cli-usage.jsonl"))
    assert names == ["cli-usage.jsonl", "cli-usage.jsonl.1", "cli-usage.jsonl.2", "cli-usage.jsonl.lock"]
    assert json.loads(_lines(target)[-1])["request_id"] == "r29"


# --- 4. безопасность (THREAT-001) -----------------------------------------------------------------------


def test_allowlist_drops_secrets_and_nested(tmp_path: Path, enabled: None) -> None:
    target = tmp_path / "d" / "cli-usage.jsonl"
    record = {
        "prompt": "secret prompt", "api_key": "sk-ZZZZZZZZZZZZZZZZ", "messages": [{"role": "user"}],
        "headers": {"Authorization": "x"}, "model": {"nested": 1}, "request_id": "Bearer sk-ABCDEF1234567890XYZ",
        "route": "a\nb\x00c" + "x" * 1000, "elapsed_ms": float("nan"), "prompt_tokens": 7,
    }
    assert CliUsageSink(str(target)).write(record) is True
    raw = target.read_text(encoding="utf-8")
    for leaked in ("secret prompt", "api_key", "sk-ABCDEF", "sk-ZZZ", "messages", "headers", "nested"):
        assert leaked not in raw
    rec = json.loads(raw)
    assert set(rec) <= set(CLI_USAGE_ALLOWLIST)
    assert "model" not in rec and "elapsed_ms" not in rec
    assert "\n" not in rec["route"] and len(rec["route"]) <= 256
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700


def test_oversized_line_rejected(tmp_path: Path, enabled: None) -> None:
    target = tmp_path / "cli-usage.jsonl"
    record = {k: "é" * 250 for k in CLI_USAGE_ALLOWLIST if k != "ts"}
    assert CliUsageSink(str(target)).write(record) is False
    assert not target.exists() or target.stat().st_size <= MAX_SINK_LINE_BYTES


# --- 5. симлинки (THREAT-004) ---------------------------------------------------------------------------


@pytest.mark.parametrize("which", ["target", "lock"])
def test_symlink_refused(tmp_path: Path, enabled: None, which: str) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    target = tmp_path / "cli-usage.jsonl"
    link = target if which == "target" else Path(str(target) + ".lock")
    link.symlink_to(victim)
    assert CliUsageSink(str(target)).write({"model": "m"}) is False
    assert victim.read_text() == "keep"
    assert link.is_symlink()


# --- 6. fail-open (THREAT-003) --------------------------------------------------------------------------


def test_unwritable_paths_fail_open(tmp_path: Path, enabled: None) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert CliUsageSink(str(blocker / "sub" / "cli-usage.jsonl")).write({"model": "m"}) is False
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        if os.access(ro, os.W_OK):  # root обходит права каталога
            pytest.skip("каталог остаётся доступным на запись")
        assert CliUsageSink(str(ro / "cli-usage.jsonl")).write({"model": "m"}) is False
    finally:
        ro.chmod(0o700)


def test_garbage_record_does_not_raise(tmp_path: Path, enabled: None) -> None:
    sink = CliUsageSink(str(tmp_path / "cli-usage.jsonl"))
    assert sink.write(None) is False  # type: ignore[arg-type]


# --- 7. парсер и эмиттер --------------------------------------------------------------------------------


def test_parse_claude_stream_json() -> None:
    raw = "\n".join([
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "result", "duration_ms": 1234, "usage": {
            "input_tokens": 10, "output_tokens": 5,
            "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20}}),
    ])
    got = parse_cli_usage_payload(raw)
    assert got is not None
    assert got["prompt_tokens"] == 130 and got["completion_tokens"] == 5 and got["total_tokens"] == 135
    assert got["cached_tokens"] == 100 and got["cache_creation_tokens"] == 20
    assert got["usage_present"] is True and got["elapsed_ms"] == 1234


def test_parse_codex_exec_json() -> None:
    raw = "\n".join([
        json.dumps({"type": "thread.started"}),
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 200, "cached_input_tokens": 150, "output_tokens": 30}}),
    ])
    got = parse_cli_usage_payload(raw)
    assert got is not None
    assert got["prompt_tokens"] == 200 and got["cached_tokens"] == 150 and got["completion_tokens"] == 30
    assert got["total_tokens"] == 230


def test_parse_usage_report_and_openai_shapes() -> None:
    flat = parse_cli_usage_payload(json.dumps({
        "model": "m1", "prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10, "cached_tokens": 4}))
    assert flat is not None and flat["model"] == "m1" and flat["cached_tokens"] == 4 and flat["total_tokens"] == 10
    wrapped = parse_cli_usage_payload(json.dumps({"usage": {
        "prompt_tokens": 8, "completion_tokens": 2, "prompt_tokens_details": {"cached_tokens": 3}}}))
    assert wrapped is not None and wrapped["cached_tokens"] == 3 and wrapped["total_tokens"] == 10


@pytest.mark.parametrize("raw", ["", "not json", "[1,2]", '{"type":"result"}', '{"usage":{"foo":1}}'])
def test_parse_no_usage_returns_none(raw: str) -> None:
    assert parse_cli_usage_payload(raw) is None


def _emit(args: list[str], stdin: str, env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **env_extra}
    return subprocess.run(
        [sys.executable, str(_EMIT), *args], input=stdin, capture_output=True, text=True, env=env, timeout=60,
    )


def test_emit_cli_writes_record_and_is_silent(tmp_path: Path) -> None:
    target = tmp_path / "cli-usage.jsonl"
    payload = json.dumps({"type": "result", "usage": {
        "input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}})
    res = _emit(["--model", "claude-x", "--path", str(target), "--elapsed-ms", "12.5"], payload, {ENABLED_ENV: "1"})
    assert res.returncode == 0 and res.stdout == ""
    rec = json.loads(_lines(target)[0])
    assert rec["prompt_tokens"] == 8 and rec["cached_tokens"] == 3 and rec["model"] == "claude-x"
    assert rec["backend_id"] == rec["route"] == rec["transport_kind"] == "cli-direct"
    assert rec["elapsed_ms"] == 12.5 and rec["request_id"]


def test_emit_cli_input_file_verbose_and_disabled(tmp_path: Path) -> None:
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"prompt_tokens": 5, "completion_tokens": 1}))
    target = tmp_path / "out" / "cli-usage.jsonl"
    off = _emit(["--input", str(src), "--path", str(target), "--verbose"], "", {ENABLED_ENV: "0"})
    assert off.returncode == 0 and json.loads(off.stdout)["written"] is False and not target.parent.exists()
    on = _emit(["--input", str(src), "--path", str(target), "--verbose"], "", {ENABLED_ENV: "1"})
    assert on.returncode == 0 and json.loads(on.stdout) == {"written": True, "usage_present": True}


def test_emit_cli_fail_open_on_missing_input_and_bad_path(tmp_path: Path) -> None:
    res = _emit(["--input", str(tmp_path / "nope.json"), "--path", "/proc/x/y.jsonl"], "", {ENABLED_ENV: "1"})
    assert res.returncode == 0 and res.stdout == ""

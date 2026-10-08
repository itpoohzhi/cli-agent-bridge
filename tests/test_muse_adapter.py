"""Тесты MuseAdapter: argv Muse CLI (включая `--yolo --trust-workspace`), разбор вывода, ошибки.

Настоящий subprocess: вместо `muse-cli.sh` — фейковая обёртка (bash), которая пишет argv/env/
prompt рядом с собой и по файлу `mode` выдаёт JSONL-сценарий. Реальный Muse, Meta и прокси
:10816 не вызываются; «прокси» — слушающий сокет на свободном порту.
"""

import hashlib
import os
import signal
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.muse_adapter import (  # noqa: E402
    ENV_ALLOWLIST,
    ExecEvents,
    MuseAdapter,
    estimate_tokens,
)
from core.backend_adapter import BackendNotSupported  # noqa: E402

TOOL_JSON = (
    '{"payload_type":"run.output.delta","payload":{"text":"<tool_call>'
    '{\\"name\\": \\"get_weather\\", \\"arguments\\": {\\"city\\": \\"Paris\\"}}'
    '</tool_call>"}}'
)

FAKE_WRAPPER = r"""#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
n=$(cat "$DIR/count" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$DIR/count"
printf '%s\n' "$@" > "$DIR/argv.$n"
env > "$DIR/env.$n"
while [ $# -gt 0 ]; do
  if [ "$1" = "--prompt-file" ]; then cp "$2" "$DIR/prompt.$n"; echo "$2" > "$DIR/promptpath.$n"; fi
  shift
done
mode=$(cat "$DIR/mode")
ok() {
  echo '{"payload_type":"run.output.delta","payload":{"text":"Hello "}}'
  echo 'not-json garbage'
  echo '{"payload_type":"run.output.delta","payload":{"text":"world"}}'
  echo '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}'
}
case "$mode" in
  ok) ok ;;
  final)
    echo '{"payload_type":"run.output.delta","payload":{"text":"partial"}}'
    echo '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed","text":"FINAL TEXT"}}' ;;
  tool)
    cat <<'EOF'
@TOOL@
{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}
EOF
    ;;
  fail42) echo "muse-cli: proxy DOWN" >&2; exit 42 ;;
  failed)
    echo '{"payload_type":"run.terminal.failed","payload":{"terminal":"failed","reason":"boom"}}' ;;
  exit1) echo "something bad" >&2; exit 1 ;;
  netonce)
    if [ "$n" -eq 1 ]; then echo "network connection could not be opened" >&2; exit 1; fi
    ok ;;
  sleep) echo $$ > "$DIR/pid"; sleep 30 ;;
esac
"""


class FakeMuse:
    """Каталог с фейковой обёрткой, счётчиком запусков и слушающим «прокси»."""

    def __init__(self, base: Path):
        self.base = base
        base.mkdir(parents=True, exist_ok=True)
        self.wrapper = base / "muse-cli.sh"
        self.wrapper.write_text(
            FAKE_WRAPPER.replace("@TOOL@", TOOL_JSON), encoding="utf-8"
        )
        self.wrapper.chmod(0o755)
        self.set_mode("ok")
        self._proxy = socket.socket()
        self._proxy.bind(("127.0.0.1", 0))
        self._proxy.listen(8)
        self.proxy_port = self._proxy.getsockname()[1]

    def set_mode(self, mode: str) -> None:
        (self.base / "mode").write_text(mode, encoding="utf-8")

    def count(self) -> int:
        try:
            return int((self.base / "count").read_text())
        except (OSError, ValueError):
            return 0

    def argv(self, n: int = 1) -> list:
        return (self.base / f"argv.{n}").read_text(encoding="utf-8").split("\n")[:-1]

    def env(self, n: int = 1) -> dict:
        lines = (self.base / f"env.{n}").read_text(encoding="utf-8").splitlines()
        return dict(line.split("=", 1) for line in lines if "=" in line)

    def close(self) -> None:
        self._proxy.close()

    def config(self, **extra) -> dict:
        config = {
            "kind": "muse",
            "enabled": True,
            "required": False,
            "owned_by": "meta-muse",
            "max_concurrent": 2,
            "wrapper": str(self.wrapper),
            "proxy_port": self.proxy_port,
        }
        config.update(extra)
        return config


def catalog_with_muse() -> dict:
    model = {"id": "muse-spark-1.3", "backend": "muse", "context_window": 1048576}
    other = {"id": "claude-sonnet-5-5", "backend": "droid", "context_window": 1}
    return {
        "order": ["claude-sonnet-5-5", "muse-spark-1.3"],
        "models": {"claude-sonnet-5-5": other, "muse-spark-1.3": model},
    }


def host_stub(tmp: Path, **extra):
    base = dict(
        WORKSPACE=tmp / "ws",
        TIMEOUT_S=30.0,
        QUEUE_TIMEOUT_S=900.0,
        KEEPALIVE_S=15.0,
        _log=lambda message: None,
    )
    base.update(extra)
    return types.SimpleNamespace(**base)


def ctx_for(prompt="hi", **extra):
    ctx = {
        "model": "muse-spark-1.3",
        "effort": "max",
        "prompt": prompt,
        "tag": "client=test",
        "emulate_tools": False,
    }
    ctx.update(extra)
    return ctx


class MuseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.fake = FakeMuse(self.tmp / "fake")
        self.addCleanup(self.fake.close)
        self.addCleanup(self._tmp.cleanup)
        self.host = host_stub(self.tmp)

    def adapter(self, host=None, **config) -> MuseAdapter:
        catalog = catalog_with_muse()
        adapter = MuseAdapter(
            "muse", self.fake.config(**config), lambda: catalog, host or self.host
        )
        self.addCleanup(adapter.shutdown)
        return adapter


class TestArgv(MuseCase):
    def test_argv_has_owner_approved_flags_and_model_effort(self):
        """AD-007: `--yolo --trust-workspace` сохранены; модель, effort и exec/--json на месте."""
        argv = self.adapter().build_argv("muse-spark-1.3", "max", "/tmp/p.txt")
        self.assertEqual(argv[0], str(self.fake.wrapper))
        self.assertEqual(argv[1], "exec")
        self.assertIn("--yolo", argv)
        self.assertIn("--trust-workspace", argv)
        self.assertIn("--json", argv)
        self.assertEqual(argv[argv.index("--provider") + 1], "meta")
        self.assertEqual(argv[argv.index("--model") + 1], "muse-spark-1.3")
        self.assertEqual(argv[argv.index("--reasoning-effort") + 1], "max")
        self.assertEqual(argv[argv.index("--prompt-file") + 1], "/tmp/p.txt")
        self.assertIn("--no-session-log", argv)

    def test_default_wrapper_is_canonical_launcher(self):
        adapter = MuseAdapter("muse", {"kind": "muse"}, catalog_with_muse)
        self.assertEqual(
            adapter.wrapper, os.path.expanduser("~/.config/muse-launch/muse-cli.sh")
        )

    def test_child_env_is_allowlist_without_secrets(self):
        secrets = {
            "META_API_KEY": "m" * 40,
            "DROID_DSH_BRIDGE_KEY": "k" * 40,
            "SOME_OTHER_SECRET": "s" * 40,
            "HOME": "/home/x",
        }
        with mock.patch.dict(os.environ, secrets):
            env = self.adapter().child_env()
        self.assertNotIn("META_API_KEY", env)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
        self.assertNotIn("SOME_OTHER_SECRET", env)
        self.assertEqual(env["HOME"], "/home/x")
        self.assertIn("PATH", env)
        self.assertTrue(set(env) <= set(ENV_ALLOWLIST))


class TestExecEvents(unittest.TestCase):
    def test_deltas_joined_and_garbage_ignored(self):
        events = ExecEvents()
        for line in (
            '{"payload_type":"run.output.delta","payload":{"text":"a"}}',
            "garbage",
            "[1,2]",
            "",
            '{"payload_type":"run.output.delta","payload":{"text":"b"}}',
            '{"payload_type":"run.terminal.completed","payload":{}}',
        ):
            events.feed_line(line)
        self.assertEqual(events.text, "ab")
        self.assertEqual(events.terminal, "completed")

    def test_final_text_has_priority_over_deltas(self):
        events = ExecEvents()
        events.feed_line('{"payload_type":"run.output.delta","payload":{"text":"x"}}')
        events.feed_line(
            '{"payload_type":"run.terminal.completed","payload":{"text":"FINAL"}}'
        )
        self.assertEqual(events.text, "FINAL")

    def test_failed_terminal_and_task_failure_reason(self):
        events = ExecEvents()
        events.feed_line(
            '{"payload_type":"task.lifecycle.failed","payload":{"event":{"reason":"r1"}}}'
        )
        events.feed_line(
            '{"payload_type":"run.terminal.failed","payload":{"terminal":"failed","reason":"boom"}}'
        )
        self.assertEqual(events.terminal, "failed")
        self.assertEqual(events.reason, "boom")
        self.assertEqual(events.errors, ["task failed: r1"])

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("one two three four five"), 6)


class TestExecuteTurn(MuseCase):
    def test_success_passes_flags_and_cleans_up(self):
        out = self.adapter().execute_turn(ctx_for("привет"), None)
        self.assertEqual((out["state"], out["rc"]), ("done", 0))
        self.assertEqual(out["text"], "Hello world")
        self.assertEqual(out["usage"]["output_tokens"], estimate_tokens("Hello world"))
        self.assertGreater(out["usage"]["input_tokens"], 0)
        argv = self.fake.argv()
        for flag in ("--yolo", "--trust-workspace", "--json", "exec"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--model") + 1], "muse-spark-1.3")
        self.assertEqual(
            (self.fake.base / "prompt.1").read_text(encoding="utf-8"), "привет"
        )
        prompt_path = (self.fake.base / "promptpath.1").read_text().strip()
        self.assertFalse(os.path.exists(prompt_path))  # prompt-файл удалён после хода
        self.assertEqual(self.adapter().active_count(), 0)

    def test_child_env_has_no_secrets_in_real_process(self):
        with mock.patch.dict(
            os.environ,
            {
                "META_API_KEY": "m" * 40,
                "DROID_DSH_BRIDGE_KEY": "k" * 40,
                "ZZ_LEAK": "z",
            },
        ):
            out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out["state"], "done")
        env = self.fake.env()
        for name in ("META_API_KEY", "DROID_DSH_BRIDGE_KEY", "ZZ_LEAK"):
            self.assertNotIn(name, env)

    def test_final_text_in_terminal_wins(self):
        self.fake.set_mode("final")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out["text"], "FINAL TEXT")

    def test_adapter_returns_raw_tool_call_text_for_facade_parsing(self):
        self.fake.set_mode("tool")
        out = self.adapter().execute_turn(ctx_for(emulate_tools=True), None)
        self.assertEqual(out["state"], "done")
        self.assertIn("<tool_call>", out["text"])
        self.assertNotIn("tool_calls", out)  # разбор блоков — дело фасада

    def test_proxy_exit_42_is_launcher_unavailable(self):
        self.fake.set_mode("fail42")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out["state"], "launcher_unavailable")
        self.assertEqual(out["rc"], 42)
        self.assertEqual(self.fake.count(), 1)  # без ретрая

    def test_failed_terminal_is_backend_error(self):
        self.fake.set_mode("failed")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out["state"], "backend_error")
        self.assertIn("boom", out["err"])

    def test_nonzero_exit_is_backend_error_and_not_retried(self):
        self.fake.set_mode("exit1")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual((out["state"], out["rc"]), ("backend_error", 1))
        self.assertIn("something bad", out["err"])
        self.assertEqual(self.fake.count(), 1)

    def test_single_retry_only_on_network_marker(self):
        self.fake.set_mode("netonce")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out["state"], "done")
        self.assertEqual(self.fake.count(), 2)

    def test_missing_wrapper_is_launcher_unavailable(self):
        adapter = self.adapter(wrapper=str(self.tmp / "no-such.sh"))
        out = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(out["state"], "launcher_unavailable")
        self.assertEqual(out["err"], "wrapper_not_executable")

    def test_proxy_down_refuses_before_spawn(self):
        adapter = self.adapter(proxy_port=1)  # порт 1 не слушается
        self.assertFalse(adapter.is_healthy())
        out = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(
            (out["state"], out["err"]), ("launcher_unavailable", "proxy_down")
        )
        self.assertEqual(self.fake.count(), 0)

    def test_timeout_kills_process_group(self):
        self.fake.set_mode("sleep")
        host = host_stub(self.tmp, TIMEOUT_S=1.0)
        started = time.monotonic()
        out = self.adapter(host).execute_turn(ctx_for(), None)
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual((out["state"], out["rc"]), ("timeout", 124))
        pid = int((self.fake.base / "pid").read_text())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_client_gone_kills_child(self):
        self.fake.set_mode("sleep")
        gone = threading.Event()
        threading.Timer(0.5, gone.set).start()
        out = self.adapter().execute_turn(ctx_for(client_gone=gone.is_set), None)
        self.assertEqual(out["state"], "client_gone")

    def test_capacity_cap_gives_queue_timeout(self):
        self.fake.set_mode("sleep")
        host = host_stub(self.tmp, QUEUE_TIMEOUT_S=1.0, TIMEOUT_S=20.0)
        adapter = self.adapter(host, max_concurrent=1)
        first: dict = {}
        gone = threading.Event()
        worker = threading.Thread(
            target=lambda: first.update(
                adapter.execute_turn(ctx_for(client_gone=gone.is_set), None)
            )
        )
        worker.start()
        deadline = time.monotonic() + 5
        while adapter.active_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        second = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(second["state"], "queue_timeout")
        gone.set()
        worker.join(timeout=10)
        self.assertEqual(first.get("state"), "client_gone")

    def test_shutdown_kills_active_child_and_refuses_new(self):
        self.fake.set_mode("sleep")
        adapter = self.adapter()
        result: dict = {}
        worker = threading.Thread(
            target=lambda: result.update(adapter.execute_turn(ctx_for(), None))
        )
        worker.start()
        deadline = time.monotonic() + 5
        while adapter.active_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        adapter.shutdown()
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(adapter.active_count(), 0)
        again = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(again["state"], "launcher_unavailable")


class TestQualify(MuseCase):
    def test_qualify_ok_without_pin(self):
        self.assertEqual(self.adapter().qualify(), (True, "ok"))
        self.assertTrue(self.adapter().is_healthy())

    def test_qualify_pin_match_and_mismatch(self):
        binary = self.tmp / "muse-bin"
        binary.write_bytes(b"muse-image")
        digest = hashlib.sha256(b"muse-image").hexdigest()
        ref = {"binary_path": str(binary), "binary_sha256": digest}
        self.assertEqual(self.adapter(technical_ref=ref).qualify(), (True, "ok"))
        ref_bad = {"binary_path": str(binary), "binary_sha256": "0" * 64}
        self.assertEqual(
            self.adapter(technical_ref=ref_bad).qualify(),
            (False, "binary_sha256_mismatch"),
        )
        binary.unlink()
        self.assertEqual(
            self.adapter(technical_ref=ref).qualify(), (False, "binary_missing")
        )

    def test_qualify_rejects_non_executable_wrapper(self):
        self.fake.wrapper.chmod(0o644)
        self.assertEqual(self.adapter().qualify(), (False, "wrapper_not_executable"))

    def test_sessions_none_and_models(self):
        adapter = self.adapter()
        with self.assertRaises(BackendNotSupported):
            adapter.spawn_session({})
        adapter.close_session("whatever")  # идемпотентно, без ошибок
        self.assertEqual([m["id"] for m in adapter.get_models()], ["muse-spark-1.3"])
        self.assertEqual(adapter.capabilities["sessions"], "none")
        self.assertFalse(adapter.capabilities["autonomy"])


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    unittest.main()

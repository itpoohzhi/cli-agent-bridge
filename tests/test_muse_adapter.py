"""Тесты MuseAdapter: argv Muse CLI (включая `--yolo --trust-workspace`), разбор вывода, ошибки.

Настоящий subprocess: вместо `muse-cli.sh` — фейковая обёртка (bash), которая пишет argv/env/
prompt рядом с собой и по файлу `mode` выдаёт JSONL-сценарий. Реальный Muse, Meta и прокси
:10816 не вызываются; «прокси» — слушающий сокет на свободном порту.

Покрываются компенсаторы AD-007: per-turn каталог хода (RW-001), очистка `MUSE_BIN` (RW-002),
отсутствие автоматического replay (RW-003), обязательный terminal.completed (RW-004), байтовые
бюджеты строки/текста и bounded failure reasons (RW-006), ограниченное завершение группы
процессов (RW-009), персистентный реестр детей (RW-010), `MUSE_PROXY_PORT` (RW-011).
"""

import hashlib
import json
from dataclasses import asdict
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
    MAX_ERR_CHARS,
    MAX_EVENT_ERRORS,
    ExecEvents,
    MuseAdapter,
    estimate_tokens,
)
from core.backend_adapter import BackendNotSupported, TurnContext  # noqa: E402
from test_hub_integration import HubCase as _HubCase  # noqa: E402

TOOL_JSON = (
    '{"payload_type":"run.output.delta","payload":{"text":"<tool_call>'
    '{\\"name\\": \\"get_weather\\", \\"arguments\\": {\\"city\\": \\"Paris\\"}}'
    '</tool_call>"}}'
)

FAKE_WRAPPER = r"""#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
n=$(cat "$DIR/count" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$DIR/count"
printf '%s\n' "$@" > "$DIR/argv.$n"
printf '%s\n' "$@" > "$DIR/argv.pid.$$"
env > "$DIR/env.$n"
env > "$DIR/env.pid.$$"
while [ $# -gt 0 ]; do
  if [ "$1" = "--prompt-file" ]; then
    cp "$2" "$DIR/prompt.$n"; echo "$2" > "$DIR/promptpath.$n"
    cp "$2" "$DIR/prompt.pid.$$"; echo "$2" > "$DIR/promptpath.pid.$$"
  fi
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
  noterminal) echo '{"payload_type":"run.output.delta","payload":{"text":"partial"}}' ;;
  contradictory)
    echo '{"payload_type":"run.terminal.failed","payload":{"terminal":"completed","text":"wrong"}}' ;;
  unknown_terminal)
    echo '{"payload_type":"run.terminal.surprise","payload":{"terminal":"completed","text":"wrong"}}' ;;
  missing_status)
    echo '{"payload_type":"run.terminal.completed","payload":{"text":"wrong"}}' ;;
  unicode)
    "@PYTHON@" -c 'import json; print(json.dumps({"payload_type":"run.terminal.completed","payload":{"terminal":"completed","text":"я"*1000}},ensure_ascii=False))' ;;
  deep)
    "@PYTHON@" -c 'print("["*2000+"0"+"]"*2000)' ;;
  struct)
    "@PYTHON@" -c 'print("["+"{},"*1000+"{}]")' ;;
  empty_flood)
    for i in $(seq 1 300); do echo '{"payload_type":"run.output.delta","payload":{"text":""}}'; done
    ok ;;
  bad_utf8)
    printf '\377\n'; ok ;;
  spy)
    find "$(dirname "$PWD")" -name prompt.txt -exec cat {} \; > "$DIR/seen.$$"
    sleep 0.5
    ok ;;
  desc_stdout)
    ok
    sleep 30 &
    echo $! > "$DIR/child.pid" ;;
  sentinel)
    echo "invalid prompt: patient John has HIV" >&2
    echo '{"payload_type":"run.terminal.failed","payload":{"terminal":"failed","reason":"invalid prompt: patient John has HIV"}}' ;;
  netonce)
    if [ "$n" -eq 1 ]; then echo "network connection could not be opened" >&2; exit 1; fi
    ok ;;
  netmarker)
    echo action >> "$DIR/action.log"
    echo "network connection could not be opened" >&2
    exit 1 ;;
  bigline)
    "@PYTHON@" -c 'import sys; sys.stdout.write("a"*9000000)'; echo ;;
  bigtext)
    chunk=$("@PYTHON@" -c 'import sys; sys.stdout.write("a"*600000)')
    for i in $(seq 1 20); do
      printf '{"payload_type":"run.output.delta","payload":{"text":"%s"}}\n' "$chunk"
    done ;;
  desc_stderr)
    echo '{"payload_type":"run.output.delta","payload":{"text":"Hello "}}'
    echo '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}'
    sleep 30 > /dev/null &
    echo $! > "$DIR/child.pid" ;;
  desc_devnull)
    echo '{"payload_type":"run.output.delta","payload":{"text":"Hello "}}'
    echo '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}'
    sleep 30 > /dev/null 2>&1 &
    echo $! > "$DIR/child.pid" ;;
  sleep) echo $$ > "$DIR/pid"; sleep 30 ;;
esac
"""


class FakeMuse:
    """Каталог с фейковой обёрткой, счётчиком запусков и слушающим «прокси»."""

    def __init__(self, base: Path):
        self.base = base
        base.mkdir(parents=True, exist_ok=True)
        self.wrapper = base / "muse-cli.sh"
        self.binary = Path(os.path.expanduser("~/.local/bin/muse"))
        self.binary.parent.mkdir(parents=True, exist_ok=True)
        self.binary.write_text(
            FAKE_WRAPPER.replace("@TOOL@", TOOL_JSON)
            .replace("@PYTHON@", sys.executable)
            .replace('DIR="$(cd "$(dirname "$0")" && pwd)"', "DIR=" + repr(str(base))),
            encoding="utf-8",
        )
        self.binary.chmod(0o755)
        self.wrapper.write_text('#!/bin/sh\nexec "$HOME/.local/bin/muse" "$@"\n')
        self.wrapper.chmod(0o755)
        self.set_mode("ok")
        self._proxy = socket.socket()
        self._proxy.bind(("127.0.0.1", 0))
        self._proxy.listen(512)
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

    def pin(self) -> dict:
        digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        return {"binary_path": str(self.binary), "binary_sha256": digest}

    def close(self) -> None:
        self._proxy.close()

    def config(self, **extra) -> dict:
        config = {
            "kind": "muse",
            "enabled": True,
            "required": False,
            "owned_by": "meta-muse",
            "max_concurrent": 1,
            "wrapper": str(self.wrapper),
            "proxy_port": self.proxy_port,
            "technical_ref": self.pin(),
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
    return TurnContext(**ctx)


def wait_pid_gone(pid: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


class MuseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        home = mock.patch.dict(os.environ, {"HOME": str(self.tmp / "home")})
        home.start()
        self.addCleanup(home.stop)
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

    def test_argv_workspace_is_prompt_directory_not_common_parent(self):
        """RW-001: `--workspace` — каталог хода (родитель prompt-файла), не общий workspace/muse."""
        argv = self.adapter().build_argv(
            "muse-spark-1.3", "max", "/tmp/turn-1/prompt.txt"
        )
        self.assertEqual(argv[argv.index("--workspace") + 1], "/tmp/turn-1")

    def test_default_wrapper_is_canonical_launcher(self):
        adapter = MuseAdapter("muse", {"kind": "muse"}, catalog_with_muse)
        self.assertEqual(
            adapter.wrapper, os.path.expanduser("~/.config/muse-launch/muse-cli.sh")
        )

    def test_child_env_is_allowlist_without_secrets(self):
        secrets = {
            "META_API_KEY": "m" * 40,
            "DROID_DSH_BRIDGE_KEY": "k" * 40,
            "BRIDGE_KEY": "k" * 40,
            "SOME_OTHER_SECRET": "s" * 40,
            "HOME": "/home/x",
        }
        with mock.patch.dict(os.environ, secrets):
            env = self.adapter().child_env()
        self.assertNotIn("META_API_KEY", env)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
        self.assertNotIn("BRIDGE_KEY", env)
        self.assertNotIn("SOME_OTHER_SECRET", env)
        self.assertEqual(env["HOME"], "/home/x")
        self.assertIn("PATH", env)
        self.assertTrue(set(env) <= set(ENV_ALLOWLIST))

    def test_child_env_scrubs_muse_bin_and_pins_proxy_port(self):
        """RW-002/RW-011: унаследованный MUSE_BIN не проходит; порт — из конфигурации бэкенда."""
        with mock.patch.dict(
            os.environ,
            {"MUSE_BIN": "/tmp/evil-muse", "MUSE_PROXY_PORT": "9999"},
        ):
            adapter = self.adapter(proxy_port=12345)
            env = adapter.child_env()
        self.assertNotIn("MUSE_BIN", env)
        self.assertEqual(env["MUSE_PROXY_PORT"], "12345")
        self.assertEqual(adapter.proxy_port, 12345)


class TestExecEvents(unittest.TestCase):
    def test_deltas_joined_and_garbage_ignored(self):
        events = ExecEvents()
        for line in (
            '{"payload_type":"run.output.delta","payload":{"text":"a"}}',
            "garbage",
            "[1,2]",
            "",
            '{"payload_type":"run.output.delta","payload":{"text":"b"}}',
            '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed"}}',
        ):
            events.feed_line(line)
        self.assertEqual(events.text, "ab")
        self.assertEqual(events.terminal, "completed")

    def test_final_text_has_priority_over_deltas(self):
        events = ExecEvents()
        events.feed_line('{"payload_type":"run.output.delta","payload":{"text":"x"}}')
        events.feed_line(
            '{"payload_type":"run.terminal.completed","payload":{"terminal":"completed","text":"FINAL"}}'
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

    def test_failure_reasons_are_bounded_and_charged(self):
        """RW-006: errors bounded до append, reason обрезан, всё списано в байтовый бюджет."""
        events = ExecEvents()
        for index in range(50):
            events.feed_line(
                '{"payload_type":"task.lifecycle.failed","payload":'
                '{"event":{"reason":"r%03d-%s"}}}' % (index, "x" * 2000)
            )
        events.feed_line(
            '{"payload_type":"run.terminal.failed","payload":'
            '{"terminal":"failed","reason":"%s"}}' % ("y" * 5000)
        )
        self.assertEqual(len(events.errors), MAX_EVENT_ERRORS)
        self.assertTrue(all(len(item) <= MAX_ERR_CHARS for item in events.errors))
        self.assertLessEqual(len(events.reason), MAX_ERR_CHARS)
        self.assertGreater(events.text_bytes, 1000)

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("one two three four five"), 6)


class TestExecuteTurn(MuseCase):
    def test_success_passes_flags_and_cleans_up(self):
        adapter = self.adapter()
        out = adapter.execute_turn(ctx_for("привет"), None)
        self.assertEqual((out.state, out.rc), ("done", 0))
        self.assertEqual(out.text, "Hello world")
        self.assertEqual(out.usage.output_tokens, estimate_tokens("Hello world"))
        self.assertGreater(out.usage.input_tokens, 0)
        argv = self.fake.argv()
        for flag in ("--yolo", "--trust-workspace", "--json", "exec"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--model") + 1], "muse-spark-1.3")
        self.assertEqual(
            (self.fake.base / "prompt.1").read_text(encoding="utf-8"), "привет"
        )
        prompt_path = Path((self.fake.base / "promptpath.1").read_text().strip())
        self.assertEqual(prompt_path.parent, Path(argv[argv.index("--workspace") + 1]))
        self.assertEqual(prompt_path.parent.parent, adapter.workspace)
        self.assertFalse(os.path.exists(prompt_path))  # prompt-файл удалён после хода
        self.assertFalse(prompt_path.parent.exists())  # каталог хода удалён целиком
        self.assertEqual(adapter.active_count(), 0)

    def test_parallel_turns_use_own_workspace_and_prompt(self):
        """RW-001: у каждого хода собственный каталог; prompt соседа недостижим по argv."""
        adapter = self.adapter(max_concurrent=1)
        results = []

        def run() -> None:
            results.append(adapter.execute_turn(ctx_for(), None))

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual([out.state for out in results], ["done", "done"])
        # Файлы, привязанные к pid процесса-обёртки: гонка счётчика не влияет.
        prompt_files = sorted(self.fake.base.glob("promptpath.pid.*"))
        argv_files = sorted(self.fake.base.glob("argv.pid.*"))
        self.assertEqual(len(prompt_files), 2)
        self.assertEqual(len(argv_files), 2)
        workspaces = []
        prompts = []
        for prompt_file, argv_file in zip(prompt_files, argv_files):
            argv = argv_file.read_text(encoding="utf-8").split("\n")[:-1]
            workspaces.append(argv[argv.index("--workspace") + 1])
            prompts.append(Path(prompt_file.read_text().strip()))
        self.assertNotEqual(workspaces[0], workspaces[1])
        self.assertNotEqual(prompts[0].parent, prompts[1].parent)
        self.assertNotEqual(prompts[0].parent, adapter.workspace)
        self.assertNotIn(prompts[0].parent, prompts[1].parents)
        self.assertNotIn(prompts[1].parent, prompts[0].parents)
        for path in prompts:
            self.assertFalse(path.exists())
            self.assertFalse(path.parent.exists())

    def test_child_env_has_no_secrets_in_real_process(self):
        with mock.patch.dict(
            os.environ,
            {
                "META_API_KEY": "m" * 40,
                "DROID_DSH_BRIDGE_KEY": "k" * 40,
                "BRIDGE_KEY": "k" * 40,
                "ZZ_LEAK": "z",
                "MUSE_BIN": "/tmp/evil-muse",
            },
        ):
            out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "done")
        env = self.fake.env()
        for name in (
            "META_API_KEY",
            "DROID_DSH_BRIDGE_KEY",
            "BRIDGE_KEY",
            "ZZ_LEAK",
            "MUSE_BIN",
        ):
            self.assertNotIn(name, env)

    def test_configured_proxy_port_is_passed_to_wrapper(self):
        """RW-011: обёртка получает ровно тот порт, который проверил preflight."""
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "done")
        self.assertEqual(self.fake.env()["MUSE_PROXY_PORT"], str(self.fake.proxy_port))

    def test_final_text_in_terminal_wins(self):
        self.fake.set_mode("final")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.text, "FINAL TEXT")

    def test_adapter_returns_raw_tool_call_text_for_facade_parsing(self):
        self.fake.set_mode("tool")
        out = self.adapter().execute_turn(ctx_for(emulate_tools=True), None)
        self.assertEqual(out.state, "done")
        self.assertIn("<tool_call>", out.text)
        self.assertEqual(out.tool_calls, ())  # разбор блоков — дело фасада

    def test_proxy_exit_42_is_launcher_unavailable(self):
        self.fake.set_mode("fail42")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "launcher_unavailable")
        self.assertEqual(out.rc, 42)
        self.assertEqual(self.fake.count(), 1)  # без ретрая

    def test_failed_terminal_is_backend_error(self):
        self.fake.set_mode("failed")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "backend_error")
        self.assertIn("boom", out.err)

    def test_missing_terminal_completed_is_backend_error(self):
        """RW-004: delta + EOF + rc=0 без terminal.completed — не done, а backend_error (502)."""
        self.fake.set_mode("noterminal")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual((out.state, out.rc), ("backend_error", 1))
        self.assertIn("terminal_missing", out.err)

    def test_nonzero_exit_is_backend_error_and_not_retried(self):
        self.fake.set_mode("exit1")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual((out.state, out.rc), ("backend_error", 1))
        self.assertIn("something bad", out.err)
        self.assertEqual(self.fake.count(), 1)

    def test_network_marker_is_not_replayed(self):
        """RW-003: действие могло исполниться до сетевой ошибки — промпт не повторяется."""
        self.fake.set_mode("netmarker")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "backend_error")
        self.assertEqual(self.fake.count(), 1)
        self.assertEqual(
            (self.fake.base / "action.log").read_text(encoding="utf-8").splitlines(),
            ["action"],
        )

    def test_network_marker_on_first_run_does_not_retry(self):
        self.fake.set_mode("netonce")
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "backend_error")
        self.assertEqual(self.fake.count(), 1)

    def test_missing_wrapper_is_launcher_unavailable(self):
        adapter = self.adapter(wrapper=str(self.tmp / "no-such.sh"))
        out = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "launcher_unavailable")
        self.assertEqual(out.err, "wrapper_not_executable")

    def test_proxy_down_refuses_before_spawn(self):
        adapter = self.adapter(proxy_port=1)  # порт 1 не слушается
        self.assertFalse(adapter.is_healthy())
        out = adapter.execute_turn(ctx_for(), None)
        self.assertEqual((out.state, out.err), ("launcher_unavailable", "proxy_down"))
        self.assertEqual(self.fake.count(), 0)

    def test_timeout_kills_process_group(self):
        self.fake.set_mode("sleep")
        host = host_stub(self.tmp, TIMEOUT_S=1.0)
        started = time.monotonic()
        out = self.adapter(host).execute_turn(ctx_for(), None)
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual((out.state, out.rc), ("timeout", 124))
        pid = int((self.fake.base / "pid").read_text())
        self.assertTrue(wait_pid_gone(pid), "process group survived timeout")

    def test_client_gone_kills_child(self):
        self.fake.set_mode("sleep")
        gone = threading.Event()
        threading.Timer(0.5, gone.set).start()
        out = self.adapter().execute_turn(ctx_for(client_gone=gone.is_set), None)
        self.assertEqual(out.state, "client_gone")

    def test_capacity_cap_gives_queue_timeout(self):
        self.fake.set_mode("sleep")
        host = host_stub(self.tmp, QUEUE_TIMEOUT_S=1.0, TIMEOUT_S=20.0)
        adapter = self.adapter(host, max_concurrent=1)
        first: dict = {}
        gone = threading.Event()
        worker = threading.Thread(
            target=lambda: first.update(
                asdict(adapter.execute_turn(ctx_for(client_gone=gone.is_set), None))
            )
        )
        worker.start()
        deadline = time.monotonic() + 5
        while adapter.active_count() == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        second = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(second.state, "queue_timeout")
        gone.set()
        worker.join(timeout=10)
        self.assertEqual(first.get("state"), "client_gone")

    def test_shutdown_kills_active_child_and_refuses_new(self):
        self.fake.set_mode("sleep")
        adapter = self.adapter()
        result: dict = {}
        worker = threading.Thread(
            target=lambda: result.update(asdict(adapter.execute_turn(ctx_for(), None)))
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
        self.assertEqual(again.state, "launcher_unavailable")

    def test_jsonl_line_over_limit_is_pump_error(self):
        """RW-006: строка > MAX_LINE_BYTES прекращает ход без роста памяти хаба."""
        self.fake.set_mode("bigline")
        adapter = self.adapter()
        started = time.monotonic()
        out = adapter.execute_turn(ctx_for(), None)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(out.state, "pump_error")
        self.assertIn("jsonl line exceeds the limit", out.err)
        self.assertEqual(adapter.active_count(), 0)

    def test_turn_text_over_budget_is_pump_error(self):
        """RW-006: суммарный текст хода > MAX_TURN_TEXT_BYTES прекращает ход."""
        self.fake.set_mode("bigtext")
        adapter = self.adapter()
        started = time.monotonic()
        out = adapter.execute_turn(ctx_for(), None)
        self.assertLess(time.monotonic() - started, 30)
        self.assertEqual(out.state, "pump_error")
        self.assertIn("turn text exceeds the limit", out.err)
        self.assertEqual(adapter.active_count(), 0)

    def test_descendant_holding_stderr_is_killed_bounded(self):
        """RW-009: лидер вышел, потомок держит stderr — добор ограничен, группа убита."""
        self.fake.set_mode("desc_stderr")
        adapter = self.adapter()
        started = time.monotonic()
        out = adapter.execute_turn(ctx_for(), None)
        elapsed = time.monotonic() - started
        self.assertEqual(out.state, "done")
        self.assertLess(elapsed, 15)
        child = int((self.fake.base / "child.pid").read_text())
        self.assertTrue(wait_pid_gone(child), "stderr-holding descendant survived")
        self.assertEqual(adapter.active_count(), 0)

    def test_descendant_with_devnull_stdio_is_killed(self):
        """RW-009: потомок с закрытыми pipe не остаётся после освобождения слота."""
        self.fake.set_mode("desc_devnull")
        adapter = self.adapter()
        started = time.monotonic()
        out = adapter.execute_turn(ctx_for(), None)
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(out.state, "done")
        child = int((self.fake.base / "child.pid").read_text())
        self.assertTrue(wait_pid_gone(child), "DEVNULL descendant survived")
        self.assertEqual(adapter.active_count(), 0)


class RegistryHost:
    """Хост-заглушка с персистентным реестром детей (RW-010)."""

    def __init__(self, base: Path):
        self.WORKSPACE = base / "ws"
        self.TIMEOUT_S = 30.0
        self.QUEUE_TIMEOUT_S = 900.0
        self.KEEPALIVE_S = 15.0
        self.calls: list = []
        self.removed_alive: list = []
        self._log = lambda message: None

    def _children_update(self, add=None, remove_pid=None) -> None:
        if remove_pid is not None and MuseAdapter._group_alive(remove_pid):
            self.removed_alive.append(remove_pid)
        self.calls.append((add, remove_pid))

    def _proc_start_sig(self, pid: int) -> str:
        return "sig-%d" % pid


class TestChildRegistry(MuseCase):
    def test_child_registered_and_unregistered(self):
        host = RegistryHost(self.tmp)
        adapter = MuseAdapter(
            "muse", self.fake.config(), lambda: catalog_with_muse(), host
        )
        self.addCleanup(adapter.shutdown)
        out = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "done")
        added = [add for add, _ in host.calls if add]
        removed = [pid for _, pid in host.calls if pid is not None]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["kind"], "muse")
        self.assertEqual(added[0]["pgid"], added[0]["pid"])
        self.assertEqual(added[0]["start"], "sig-%d" % added[0]["pid"])
        self.assertEqual(len(added[0]["members"]), 1)
        self.assertIn(added[0]["pid"], removed)

    def test_host_without_registry_hooks_still_runs(self):
        out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "done")


class TestQualify(MuseCase):
    def test_qualify_ok_with_complete_pin(self):
        self.assertEqual(self.adapter().qualify(), (True, "ok"))
        self.assertTrue(self.adapter().is_healthy())

    def test_qualify_requires_complete_pin(self):
        """RW-002: без комплектного pin допуск не выдаётся — ход не запускается."""
        self.assertEqual(
            self.adapter(technical_ref=None).qualify(), (False, "pin_missing")
        )
        self.assertEqual(
            self.adapter(technical_ref={"binary_path": "/tmp/x"}).qualify(),
            (False, "pin_missing"),
        )
        self.assertEqual(
            self.adapter(technical_ref={"binary_sha256": "0" * 64}).qualify(),
            (False, "pin_missing"),
        )
        out = self.adapter(technical_ref=None).execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "launcher_unavailable")
        self.assertEqual(out.err, "pin_missing")
        self.assertEqual(self.fake.count(), 0)

    def test_qualify_pin_match_and_mismatch(self):
        binary = self.fake.binary
        binary.write_bytes(b"muse-image")
        digest = hashlib.sha256(b"muse-image").hexdigest()
        ref = {"binary_path": str(binary), "binary_sha256": digest}
        self.assertEqual(self.adapter(technical_ref=ref).qualify(), (True, "ok"))
        ref_bad = {"binary_path": str(binary), "binary_sha256": "0" * 64}
        self.assertEqual(
            self.adapter(technical_ref=ref_bad).qualify(),
            (False, "binary_sha256_mismatch"),
        )
        adapter = self.adapter(technical_ref=ref)
        binary.unlink()
        self.assertEqual(adapter.qualify(), (False, "binary_missing"))

    def test_qualify_rejects_non_executable_wrapper(self):
        self.fake.wrapper.chmod(0o644)
        self.assertEqual(self.adapter().qualify(), (False, "wrapper_not_executable"))

    def test_sessions_none_and_models(self):
        adapter = self.adapter()
        with self.assertRaises(BackendNotSupported):
            adapter.spawn_session(ctx_for())
        adapter.close_session("whatever")  # идемпотентно, без ошибок
        self.assertEqual([m.id for m in adapter.get_models()], ["muse-spark-1.3"])
        self.assertEqual(adapter.capabilities.sessions, "none")
        self.assertFalse(adapter.capabilities.autonomy)


class TestPanelRework(MuseCase):
    def test_terminal_envelopes_fail_closed(self):
        for mode in ("contradictory", "unknown_terminal", "missing_status"):
            with self.subTest(mode=mode):
                self.fake.set_mode(mode)
                out = self.adapter().execute_turn(ctx_for(), None)
                self.assertEqual(out.state, "pump_error")

    def test_pin_must_name_canonical_home_binary(self):
        ref = {
            "binary_path": str(self.fake.wrapper),
            "binary_sha256": hashlib.sha256(self.fake.wrapper.read_bytes()).hexdigest(),
        }
        out = self.adapter(technical_ref=ref).execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "launcher_unavailable")
        self.assertEqual(out.err, "binary_path_not_canonical")
        self.assertEqual(self.fake.count(), 0)

    def test_cap_above_one_is_refused(self):
        with self.assertRaisesRegex(ValueError, "muse_max_concurrent"):
            self.adapter(max_concurrent=2)

    def test_untrusted_output_is_bounded(self):
        import adapters.muse_adapter as muse_module

        for mode, limits in (
            ("unicode", {"MAX_LINE_BYTES": 1800}),
            ("deep", {"MAX_LINE_BYTES": 10000}),
            ("struct", {"MAX_JSON_STRUCT_TOKENS": 100}),
            ("empty_flood", {"MAX_EVENTS": 128}),
            ("bad_utf8", {"MAX_LINE_BYTES": 10000}),
        ):
            with (
                self.subTest(mode=mode),
                mock.patch.multiple(muse_module, create=True, **limits),
            ):
                self.fake.set_mode(mode)
                out = self.adapter().execute_turn(ctx_for(), None)
                self.assertEqual(out.state, "pump_error")

    def test_empty_deltas_do_not_accumulate(self):
        events = ExecEvents()
        for _ in range(100):
            events.feed_line(
                '{"payload_type":"run.output.delta","payload":{"text":""}}'
            )
        self.assertEqual(events.deltas, [])

    def test_stdout_holding_child_is_drained_in_five_seconds(self):
        self.fake.set_mode("desc_stdout")
        started = time.monotonic()
        out = self.adapter(host_stub(self.tmp, TIMEOUT_S=20)).execute_turn(
            ctx_for(), None
        )
        self.assertEqual(out.state, "done")
        self.assertLess(time.monotonic() - started, 12)
        child = int((self.fake.base / "child.pid").read_text())
        self.assertTrue(wait_pid_gone(child))

    def test_each_thread_start_failure_cleans_group_before_unregister(self):
        for failing in (1, 2):
            with self.subTest(thread=failing):
                host = RegistryHost(self.tmp)
                adapter = self.adapter(host)
                real_start = threading.Thread.start
                calls = [0]

                def start(thread):
                    calls[0] += 1
                    if calls[0] == failing:
                        raise RuntimeError("injected start failure")
                    return real_start(thread)

                self.fake.set_mode("sleep")
                with mock.patch.object(threading.Thread, "start", start):
                    out = adapter.execute_turn(ctx_for(), None)
                self.assertEqual(out.state, "pump_error")
                self.assertEqual(adapter.active_count(), 0)
                self.assertEqual(host.removed_alive, [])
                for add, _ in host.calls:
                    if add:
                        self.assertFalse(adapter._group_alive(add["pgid"]))

    def test_typed_seam_is_available(self):
        import core.backend_adapter as backend

        for name in ("TurnContext", "TurnResult", "Capabilities", "Qualification"):
            self.assertTrue(hasattr(backend, name), name)

    def test_pin_is_checked_after_slot_before_spawn(self):
        adapter = self.adapter()
        acquire = adapter._acquire_slot

        def replace_in_queue(ctx):
            reason = acquire(ctx)
            self.fake.binary.write_text(
                self.fake.binary.read_text() + "\n# replaced while queued\n"
            )
            return reason

        with mock.patch.object(adapter, "_acquire_slot", replace_in_queue):
            out = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "launcher_unavailable")
        self.assertEqual(out.err, "binary_sha256_mismatch")
        self.assertEqual(self.fake.count(), 0)

    def test_two_backends_serialize_same_uid_workspace_and_cannot_read_neighbor(self):
        self.fake.set_mode("spy")
        first = self.adapter()
        second = self.adapter()
        results = []
        workers = [
            threading.Thread(
                target=lambda a=a, p=p: results.append(a.execute_turn(ctx_for(p), None))
            )
            for a, p in ((first, "prompt-one"), (second, "prompt-two"))
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
            self.assertFalse(worker.is_alive())
        self.assertEqual([r.state for r in results], ["done", "done"])
        seen = sorted(p.read_text() for p in self.fake.base.glob("seen.*"))
        self.assertEqual(seen, ["prompt-one", "prompt-two"])


FAKE_MSP = r"""
import json, os, re, signal, sys, time
from pathlib import Path
base = Path(@BASE@)
n = int((base / "count").read_text()) + 1 if (base / "count").exists() else 1
(base / "count").write_text(str(n))
(base / f"argv.{n}").write_text("\n".join(sys.argv[1:]) + "\n")
mode = (base / "mode").read_text()
def emit(method, params):
    print(json.dumps({"jsonrpc":"2.0", "method":method, "params":params}), flush=True)
def reply(req, result):
    print(json.dumps({"jsonrpc":"2.0", "id":req["id"], "result":result}), flush=True)
if sys.argv[1] == "exec":
    print('{"payload_type":"run.terminal.completed","payload":{"terminal":"completed","text":"EXEC"}}', flush=True)
    sys.exit(0)
if "--workspace" in sys.argv or "--yolo" in sys.argv:
    print("unsupported serve flag", file=sys.stderr)
    sys.exit(2)
(base / "workspace").write_text(os.getcwd())
(base / "permissions").write_text(str(os.stat(os.getcwd()).st_mode & 0o777))
(base / "pid").write_text(str(os.getpid()))
for line in sys.stdin:
    req = json.loads(line)
    method = req["method"]
    if method == "initialize":
        if not re.fullmatch(r"[a-z0-9_]+", req["params"]["clientInfo"]["name"]):
            print(json.dumps({"jsonrpc":"2.0", "id":req["id"], "error":{"code":-32602}}), flush=True)
            continue
        if mode == "stderr":
            os.write(2, b"E" * (512 << 10))
        if mode == "bad_pre":
            print("broken json", flush=True)
            continue
        reply(req, {"schema":{"version":2 if mode == "version" else 1}})
    elif method == "session/start":
        reply(req, {"session":{"sessionId":"session"}})
        if mode == "stdin_block":
            emit("item/started", {"item":{"itemId":"r", "kind":"reasoning"}})
            for _ in range(2000):
                emit("item/delta", {"itemId":"r", "field":"summary.0", "delta":"x"})
            time.sleep(30)
    elif method == "turn/start":
        (base / f"prompt.{n}").write_text(req["params"]["input"][0]["text"])
        reply(req, {"status":"accepted", "turnId":"turn"})
        if mode == "hang":
            time.sleep(30)
        if mode == "bad_after":
            emit("item/started", {"item":{"itemId":"tool", "kind":"toolCall", "toolName":"shell"}})
            (base / "mutation").write_text("one mutation")
        if mode in ("bad_after", "lost_tool"):
            print("broken json", flush=True)
            continue
        if mode == "approval":
            emit("approval/requested", {"approvalId":"a", "currentRequirementId":"r", "availableChoices":[{"choiceId":"yes", "decision":"approved"}]})
            decision = json.loads(next(sys.stdin))
            (base / "decision").write_text(json.dumps(decision))
            reply(decision, {})
        if mode == "oversize":
            print("x" * 20000, flush=True)
            continue
        emit("item/started", {"item":{"itemId":"r", "kind":"reasoning"}})
        parts = ["думаю🙂", " дальше", " end"] if mode != "flood" else ["x"] * 2000
        for piece in parts:
            emit("item/delta", {"itemId":"r", "field":"summary.0", "delta":piece})
            if mode != "flood":
                time.sleep(0.3 if mode == "detach" else 0.1)
        summary = "".join(parts) + " tail"
        emit("item/completed", {"item":{"itemId":"r", "kind":"reasoning", "summary":[summary]}})
        emit("item/completed", {"item":{"itemId":"answer", "kind":"agentMessage", "text":"ANSWER"}})
        if mode == "descendant":
            ready_r, ready_w = os.pipe()
            child = os.fork()
            if child == 0:
                os.close(ready_r)
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                os.write(ready_w, b"1")
                os.close(ready_w)
                time.sleep(30)
                os._exit(0)
            os.close(ready_w)
            os.read(ready_r, 1)
            os.close(ready_r)
            (base / "child.pid").write_text(str(child))
        # Процесс продолжает обслуживать RPC после terminal, как настоящий serve.
        emit("turn/completed", {"turnId":"turn", "terminal":"completed"})
"""


class TestNativeServe(MuseCase):
    def setUp(self):
        super().setUp()
        self.fake.binary.write_text(
            "#!"
            + sys.executable
            + "\n"
            + FAKE_MSP.replace("@BASE@", repr(str(self.fake.base)))
        )

    def native(self, **config):
        return self.adapter(options={"streaming_mode": "serve"}, **config)

    def test_ver_001_options_validation_and_capability(self):
        from core.backend_adapter import BACKEND_KEYS, backend_entry_error

        self.assertIn("options", BACKEND_KEYS)
        for mode, expected in (("exec", "emulated"), ("serve", "native")):
            config = self.fake.config(options={"streaming_mode": mode})
            self.assertEqual(
                backend_entry_error("muse", config, {"muse": MuseAdapter}), ""
            )
            self.assertEqual(
                self.adapter(options=config["options"]).capabilities.streaming, expected
            )
        self.assertEqual(self.adapter().capabilities.streaming, "emulated")
        for options in (
            {"streaming_mode": "bad"},
            {"streaming_mode": None},
            {"unknown": 1},
            [],
            None,
        ):
            self.assertTrue(
                backend_entry_error(
                    "muse", self.fake.config(options=options), {"muse": MuseAdapter}
                )
            )

    def test_ver_002_real_stdio_deltas_and_completed_tail(self):
        live = []
        result = self.native().execute_turn(
            ctx_for(), lambda kind, piece: live.append((kind, piece)) or True
        )
        self.assertEqual((result.state, result.text), ("done", "ANSWER"))
        self.assertEqual(result.reasoning, "думаю🙂 дальше end tail")
        self.assertTrue(live)
        self.assertTrue(
            result.reasoning.startswith("".join(piece for _, piece in live))
        )
        self.assertTrue(all(kind == "reasoning" for kind, _ in live))

    def test_ver_004_nonstream_accumulates_and_next_prompt_has_no_reasoning(self):
        adapter = self.native()
        first = adapter.execute_turn(ctx_for("first"), None)
        second = adapter.execute_turn(ctx_for("second"), None)
        self.assertEqual(first.reasoning, second.reasoning)
        self.assertTrue(first.reasoning)
        self.assertEqual((self.fake.base / "prompt.2").read_text(), "second")

    def test_ver_005_slow_client_does_not_block_stdout_and_degrades(self):
        import adapters.muse_adapter as module

        observed = []
        original = module._LiveSink

        class Captured(original):
            def __init__(self, writer):
                super().__init__(writer)
                observed.append(self)

        calls = []

        def slow(kind, text):
            calls.append(text)
            time.sleep(module.LIVE_WRITE_TIMEOUT_S + 0.1)
            return True

        self.fake.set_mode("flood")
        with mock.patch.object(module, "_LiveSink", Captured):
            result = self.native().execute_turn(ctx_for(), slow)
        self.assertEqual((result.state, result.text), ("done", "ANSWER"))
        self.assertEqual(result.reasoning, "x" * 2000 + " tail")
        self.assertTrue(observed[0].live_degraded.is_set())
        self.assertLessEqual(len(calls), 1)

    def test_ver_006_private_workspace_group_registry_and_cleanup(self):
        host = RegistryHost(self.tmp)
        adapter = self.native(host=host)
        with (
            mock.patch(
                "adapters.muse_adapter.subprocess.Popen",
                wraps=__import__("subprocess").Popen,
            ) as spawn,
            mock.patch("adapters.muse_adapter.os.killpg", wraps=os.killpg) as killpg,
        ):
            result = adapter.execute_turn(ctx_for(), None)
        self.assertEqual(result.state, "done")
        self.assertTrue(
            any(call.kwargs.get("start_new_session") for call in spawn.call_args_list)
        )
        workdir = Path((self.fake.base / "workspace").read_text())
        self.assertEqual(workdir.parent.resolve(), adapter.workspace.resolve())
        self.assertEqual((self.fake.base / "permissions").read_text(), str(0o700))
        self.assertFalse(workdir.exists())
        self.assertEqual(host.removed_alive, [])
        self.assertFalse(
            adapter._group_alive(int((self.fake.base / "pid").read_text()))
        )
        self.assertTrue(
            any(call.args[1] == signal.SIGTERM for call in killpg.call_args_list)
        )
        self.assertEqual(adapter.active_count(), 0)

    def test_ver_006_error_timeout_and_thread_start_failures_cleanup(self):
        for mode in ("hang", "bad_after"):
            with self.subTest(mode=mode):
                self.fake.set_mode(mode)
                adapter = self.native(host=host_stub(self.tmp, TIMEOUT_S=0.8))
                result = adapter.execute_turn(ctx_for(), None)
                self.assertEqual(
                    result.state, "timeout" if mode == "hang" else "backend_error"
                )
                self.assertEqual(adapter.active_count(), 0)
                self.assertFalse(list(adapter.workspace.glob("turn-*")))
                self.assertFalse(
                    adapter._group_alive(int((self.fake.base / "pid").read_text()))
                )
        self.fake.set_mode("ok")
        for failing in (1, 2, 3, 4):
            with self.subTest(thread=failing):
                host = RegistryHost(self.tmp)
                adapter = self.native(host=host)
                original_start = threading.Thread.start
                count = 0

                def start(thread):
                    nonlocal count
                    count += 1
                    if count == failing:
                        raise RuntimeError("injected start failure")
                    return original_start(thread)

                with (
                    mock.patch.object(threading.Thread, "start", start),
                    mock.patch.object(
                        adapter,
                        "_run_exec",
                        return_value=adapter._result("backend_error", 1),
                    ),
                ):
                    adapter.execute_turn(ctx_for(), lambda *_: True)
                self.assertEqual(adapter.active_count(), 0)
                self.assertFalse(list(adapter.workspace.glob("turn-*")))
                self.assertEqual(host.removed_alive, [])
                for add, _ in host.calls:
                    if add:
                        self.assertFalse(adapter._group_alive(add["pgid"]))

    def test_ver_006_sigterm_ignoring_descendant_is_killed_before_slot_release(self):
        self.fake.set_mode("descendant")
        host = RegistryHost(self.tmp)
        with mock.patch("adapters.muse_adapter.os.killpg", wraps=os.killpg) as killpg:
            result = self.native(host=host).execute_turn(ctx_for(), None)
        self.assertEqual(result.state, "done")
        self.assertTrue(
            any(call.args[1] == signal.SIGKILL for call in killpg.call_args_list)
        )
        self.assertTrue(wait_pid_gone(int((self.fake.base / "child.pid").read_text())))
        self.assertEqual(host.removed_alive, [])

    def test_ver_008_disconnect_detaches_or_kills_by_context(self):
        for detach in (True, False):
            with self.subTest(detach=detach):
                gone = threading.Event()
                activity = []
                timer = threading.Timer(0.15, gone.set)
                timer.start()
                try:
                    result = self.native().execute_turn(
                        ctx_for(
                            client_gone=gone.is_set,
                            detach_on_disconnect=detach,
                            on_activity=activity.append,
                        ),
                        lambda *_: True,
                    )
                finally:
                    timer.cancel()
                if detach:
                    self.assertEqual((result.state, result.text), ("done", "ANSWER"))
                    self.assertEqual(activity.count("detached"), 1)
                else:
                    self.assertEqual(result.state, "client_gone")

    def test_ver_009_oversize_ndjson_is_bounded_and_not_replayed(self):
        self.fake.set_mode("oversize")
        with mock.patch("adapters.muse_adapter.MAX_LINE_BYTES", 4096):
            result = self.native().execute_turn(ctx_for(), None)
        self.assertEqual(result.state, "backend_error")
        self.assertEqual(self.fake.count(), 1)

    def test_ver_010_handshake_fallback_is_safe_and_tool_failure_never_replays(self):
        for mode in ("version", "bad_pre", "bad_after", "lost_tool"):
            with self.subTest(mode=mode):
                before = self.fake.count()
                self.fake.set_mode(mode)
                result = self.native().execute_turn(ctx_for(), None)
                if mode in ("version", "bad_pre"):
                    self.assertEqual((result.state, result.text), ("done", "EXEC"))
                    self.assertEqual(self.fake.count() - before, 2)
                else:
                    self.assertEqual(result.state, "backend_error")
                    self.assertEqual(self.fake.count() - before, 1)
        self.assertEqual((self.fake.base / "mutation").read_text(), "one mutation")

    def test_ver_010_stderr_flood_and_nonblocking_approval(self):
        for mode in ("stderr", "approval"):
            with self.subTest(mode=mode):
                self.fake.set_mode(mode)
                result = self.native().execute_turn(ctx_for(), None)
                self.assertEqual((result.state, result.text), ("done", "ANSWER"))
        decision = json.loads((self.fake.base / "decision").read_text())
        self.assertEqual(decision["method"], "approval/decide")
        self.assertEqual(decision["params"]["choiceId"], "yes")

    def test_ver_010_blocked_stdin_does_not_block_stdout_or_cleanup(self):
        self.fake.set_mode("stdin_block")
        started = time.monotonic()
        with mock.patch("adapters.muse_adapter.MSP_SETUP_TIMEOUT_S", 0.5):
            result = self.native().execute_turn(ctx_for("p" * (2 << 20)), None)
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(result.state, "backend_error")
        self.assertEqual(result.reasoning, "x" * 2000)
        self.assertEqual(self.fake.count(), 1)


class TestLiveQueue(unittest.TestCase):
    def test_ver_007_count_and_byte_limits_are_nonblocking(self):
        from adapters.muse_adapter import _LiveSink, LIVE_QUEUE_MAX_BYTES

        for text, number in (("x", 2000), ("я" * (1 << 19), 3)):
            with self.subTest(bytes=len(text.encode())):
                sink = _LiveSink(None)
                # Остановленный потребитель, без доступа к настоящему сокету.
                sink.writer = lambda *_: True
                started = time.monotonic()
                for _ in range(number):
                    sink.offer(text)
                self.assertLess(time.monotonic() - started, 1)
                self.assertTrue(sink.live_degraded.is_set())
                self.assertLessEqual(sink.queue.qsize(), 1000)
                self.assertLessEqual(sink.queued_bytes, LIVE_QUEUE_MAX_BYTES)
                while not sink.queue.empty():
                    self.assertLessEqual(len(sink.queue.get_nowait().encode()), 8192)


class TestNativeHttp(_HubCase):
    """Настоящий HTTP-фасад и subprocess MSP, без вызова вендорской модели."""

    def setUp(self):
        super().setUp()
        from core.backend_adapter import AdapterRegistry
        from adapters import ADAPTER_KINDS
        import server

        self.fake_muse.binary.write_text(
            "#!"
            + sys.executable
            + "\n"
            + FAKE_MSP.replace("@BASE@", repr(str(self.fake_muse.base)))
        )
        catalog = server.FLEET
        catalog["backends"]["muse"].update(
            options={"streaming_mode": "serve"}, technical_ref=self.fake_muse.pin()
        )
        self.registry = AdapterRegistry.from_fleet(
            catalog, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        server.BACKENDS = self.registry

    def test_ver_011_http_sse_and_json_deliver_identical_reasoning_without_duplication(
        self,
    ):
        body = {
            "model": "muse-spark-1.3",
            "messages": [{"role": "user", "content": "calculate"}],
        }
        status, stream = self._post(dict(body, stream=True))
        self.assertEqual(status, 200)
        chunks = [
            json.loads(line[6:])
            for line in stream.splitlines()
            if line.startswith("data: {")
        ]
        self.assertFalse(any("error" in chunk for chunk in chunks), stream)
        deltas = [chunk["choices"][0]["delta"] for chunk in chunks]
        self.assertEqual(
            "".join(d.get("reasoning_content", "") for d in deltas),
            "думаю🙂 дальше end tail",
        )
        self.assertEqual("".join(d.get("content", "") for d in deltas), "ANSWER")
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
        status, result = self._post_json(body)
        self.assertEqual(status, 200)
        self.assertEqual(
            result["choices"][0]["message"]["reasoning_content"],
            "думаю🙂 дальше end tail",
        )

    def test_ver_008_http_disconnect_runs_detached_and_commits_once(self):
        import http.client
        import server

        self.fake_muse.set_mode("detach")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(
                {
                    "model": "muse-spark-1.3",
                    "stream": True,
                    "messages": [{"role": "user", "content": "detach"}],
                }
            ),
            {"Authorization": "Bearer test-key", "Content-Type": "application/json"},
        )
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        tid = response.getheader("X-Turn-Id")
        self.assertTrue(tid)
        response.close()
        conn.close()
        turn = server.TURN_MANAGER.get_turn(tid)
        deadline = time.monotonic() + 3
        detached_seen = False
        while time.monotonic() < deadline:
            detached_seen |= turn.status == "RUNNING_DETACHED"
            if turn.done_event.wait(0.02):
                break
        self.assertTrue(detached_seen)
        self.assertTrue(turn.done_event.is_set())
        self.assertEqual(turn.status, "COMPLETED")
        self.assertEqual(turn.buffer.get_content_text(), "ANSWER")
        self.assertEqual(turn.buffer.get_reasoning_text(), "думаю🙂 дальше end tail")
        count = self.fake_muse.count()
        final_seq = turn.buffer.last_seq
        server.TURN_MANAGER.complete_turn_from_result(
            turn, turn.result, backend_kind="muse"
        )
        self.assertEqual(turn.buffer.last_seq, final_seq)
        self.assertEqual(self.fake_muse.count(), count)


class TestSseFacadeOracles(unittest.TestCase):
    def handler(self):
        import server

        handler = server.Handler.__new__(server.Handler)
        handler._context_pruned = False
        handler.send_response = lambda *_: None
        handler.send_header = lambda *_: None
        handler.end_headers = lambda: None
        handler._reserve_delivery = lambda _: None
        handler.connection = mock.Mock()
        handler.connection.gettimeout.return_value = 30.0
        return handler

    def out(self, reasoning):
        return {
            "state": "done",
            "rc": 0,
            "text": "ANSWER",
            "reasoning": reasoning,
            "backend_kind": "muse",
            "err": "",
            "usage": {},
            "tool_calls": [],
            "events": [("reasoning", reasoning), ("content", "ANSWER")],
        }

    def test_ver_011_sse_prefix_is_not_duplicated_in_final_tail(self):
        for prefix in ("", "думаю🙂", "думаю🙂 хвост"):
            with self.subTest(prefix=prefix):
                h = self.handler()
                frames = []
                h._emit = lambda text: frames.append(text) or True

                def dispatch(ctx, keepalive, writer):
                    if prefix:
                        self.assertTrue(writer("reasoning", prefix))
                    return self.out("думаю🙂 хвост")

                h._dispatch = dispatch
                h._serve_sse({"model": "muse"})
                deltas = [
                    json.loads(f[6:])["choices"][0]["delta"]
                    for f in frames
                    if f.startswith("data: {")
                ]
                self.assertEqual(
                    "".join(d.get("reasoning_content", "") for d in deltas),
                    "думаю🙂 хвост",
                )
                self.assertEqual(
                    "".join(d.get("content", "") for d in deltas), "ANSWER"
                )
                self.assertEqual(frames[-1], "data: [DONE]\n\n")

    def test_ver_011_nonstream_json_returns_reasoning_content(self):
        import io

        h = self.handler()
        h.wfile = io.BytesIO()
        h._dispatch = lambda *_: self.out("мысли🙂")
        h._serve_json({"model": "muse"})
        message = json.loads(h.wfile.getvalue())["choices"][0]["message"]
        self.assertEqual(message["reasoning_content"], "мысли🙂")
        self.assertEqual(message["content"], "ANSWER")

    def test_ver_012_socket_lock_serializes_keepalive_live_and_terminal_and_closes_sink(
        self,
    ):
        h = self.handler()
        frames = []
        active = 0
        maximum = 0
        started = threading.Event()
        workers = []
        saved = []

        def emit(text):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if "reasoning_content" in text:
                started.set()
                time.sleep(0.08)
            frames.append(text)
            active -= 1
            return True

        def dispatch(ctx, keepalive, writer):
            saved.append(writer)
            consumer = threading.Thread(target=lambda: writer("reasoning", "live"))
            workers.append(consumer)
            consumer.start()
            self.assertTrue(started.wait(2))
            ka = threading.Thread(target=keepalive)
            workers.append(ka)
            ka.start()
            # Эмулируем истекший consumer.join: фасад обязан дождаться общего lock.
            return self.out("live tail")

        h._emit, h._dispatch = emit, dispatch
        h._serve_sse({"model": "muse"})
        for worker in workers:
            worker.join(2)
            self.assertFalse(worker.is_alive())
        before = len(frames)
        self.assertFalse(saved[0]("reasoning", "late"))
        self.assertEqual(len(frames), before)
        self.assertEqual(maximum, 1)
        self.assertEqual(frames[-1], "data: [DONE]\n\n")


class TestMspOracles(unittest.TestCase):
    """Оракулы чистого MSP-парсера из ADR 0012, без настоящего Muse."""

    def parser(self, **limits):
        from adapters.muse_msp import MspEvents

        return MspEvents(
            reasoning_cap=limits.get("reasoning_cap", 8 << 20), answer_cap=2 << 20
        )

    def started(self, parser, iid="r", kind="reasoning", **fields):
        return parser.feed(
            "item/started", {"item": {"itemId": iid, "kind": kind, **fields}}
        )

    def delta(self, parser, text, iid="r", index=0):
        return parser.feed(
            "item/delta", {"itemId": iid, "field": f"summary.{index}", "delta": text}
        )

    def completed(self, parser, summary, iid="r"):
        return parser.feed(
            "item/completed",
            {"item": {"itemId": iid, "kind": "reasoning", "summary": summary}},
        )

    def test_ver_002_incremental_keys_and_completed_snapshots(self):
        parser = self.parser()
        self.started(parser)
        self.assertEqual(self.delta(parser, "А"), "А")
        self.assertEqual(self.delta(parser, "Б"), "Б")
        self.assertEqual(self.delta(parser, "В", index=1), "\n\nВ")
        self.assertEqual(self.completed(parser, ["АБ", "ВГ"]), "Г")
        self.assertEqual(self.completed(parser, ["АБ", "ВГ"]), "")
        self.assertEqual(parser.reasoning, "АБ\n\nВГ")
        self.completed(parser, ["snapshot only"], iid="new")
        self.assertEqual(parser.reasoning, "АБ\n\nВГ\n\nsnapshot only")

    def test_summary_sentences_are_separated_in_stream(self) -> None:
        parser = self.parser()
        self.started(parser)
        first = self.delta(parser, "Gathering context.")
        second = self.delta(parser, "Resolving", index=1)
        tail = self.delta(parser, " dependencies.", index=1)
        self.assertEqual(second, "\n\nResolving")
        self.assertEqual(tail, " dependencies.")
        expected = "Gathering context.\n\nResolving dependencies."
        self.assertEqual(first + second + tail, expected)
        self.assertEqual(parser.reasoning, expected)
        self.assertEqual(
            self.completed(parser, ["Gathering context.", "Resolving dependencies."]),
            "",
        )

    def test_summary_separator_respects_existing_newlines(self) -> None:
        for chunks, separator in (
            (("First.",), "\n\n"),
            (("First.\n",), "\n"),
            (("First.\n\n",), ""),
            (("First.", "\n", "\n"), ""),
        ):
            for new_item in (False, True):
                with self.subTest(chunks=chunks, new_item=new_item):
                    parser = self.parser()
                    self.started(parser)
                    for chunk in chunks:
                        self.delta(parser, chunk)
                    if new_item:
                        emitted = self.completed(parser, ["Second."], iid="new")
                    else:
                        emitted = self.delta(parser, "Second.", index=1)
                    self.assertEqual(emitted, separator + "Second.")
                    self.assertEqual(parser.reasoning, "First.\n\nSecond.")

    def test_empty_summary_does_not_emit_separator(self) -> None:
        parser = self.parser()
        self.started(parser)
        self.delta(parser, "First.")
        self.assertEqual(self.delta(parser, "", index=1), "")
        self.assertEqual(self.completed(parser, [""], iid="empty"), "")
        self.assertEqual(parser.reasoning, "First.")

    def test_empty_first_summary_delta_preserves_later_separator(self) -> None:
        parser = self.parser()
        self.started(parser)
        first = self.delta(parser, "First.")
        empty = self.delta(parser, "", index=1)
        self.assertEqual(empty, "")
        self.assertEqual(parser.reasoning, "First.")
        second = self.delta(parser, "Second.", index=1)
        self.assertEqual(second, "\n\nSecond.")
        self.assertEqual(first + empty + second, "First.\n\nSecond.")
        self.assertEqual(parser.reasoning, "First.\n\nSecond.")
        self.assertEqual(self.completed(parser, ["First.", "Second."]), "")

    def test_ver_002_divergent_snapshot_preserves_prefix_and_tracking_is_bounded(self):
        from adapters.muse_msp import MAX_TRACKED_ITEMS

        parser = self.parser()
        self.started(parser)
        self.delta(parser, "sent prefix")
        self.completed(parser, ["replacement"])
        self.assertTrue(parser.live_degraded)
        self.assertTrue(parser.reasoning.startswith("sent prefix"))
        self.assertNotIn("replacement", parser.reasoning)
        for index in range(MAX_TRACKED_ITEMS + 2):
            self.started(parser, iid=str(index))
            self.delta(parser, "x", iid=str(index))
        self.assertLessEqual(parser.tracked_count, MAX_TRACKED_ITEMS)

    def test_ver_003_tool_markers_are_sanitized_deduplicated_and_private(self):
        for name, safe in (
            ("shell.run", "shell.run"),
            ("bad\nname", "unknown_tool"),
            ("x" * 65, "unknown_tool"),
        ):
            with self.subTest(name=name):
                parser = self.parser()
                params = {
                    "item": {
                        "itemId": "t",
                        "kind": "toolCall",
                        "toolName": name,
                        "arguments": "TOP_SECRET",
                    }
                }
                parser.feed("item/started", params)
                parser.feed("item/started", params)
                parser.feed("item/completed", params)
                parser.feed("item/completed", params)
                self.assertEqual(
                    parser.reasoning,
                    f"[Вызов инструмента: {safe}]\n[Инструмент {safe} завершён]\n",
                )
                self.assertTrue(parser.has_executed_tool)
                self.assertNotIn("TOP_SECRET", parser.reasoning)

    def test_ver_004_reasoning_budget_includes_markers_and_truncates_once(self):
        from adapters.muse_msp import REASONING_TRUNCATED

        parser = self.parser(reasoning_cap=180)
        self.started(parser, iid="t", kind="toolCall", toolName="shell")
        self.started(parser)
        self.delta(parser, "я" * 2000)
        self.delta(parser, "more" * 2000)
        self.assertLessEqual(len(parser.reasoning.encode()), 180)
        self.assertEqual(parser.reasoning.count(REASONING_TRUNCATED), 1)
        parser.feed(
            "item/completed",
            {"item": {"itemId": "a", "kind": "agentMessage", "text": "answer"}},
        )
        self.assertEqual(parser.text, "answer")

    def test_ver_009_utf8_slices_reassemble_exactly(self):
        from adapters.muse_msp import utf8_slices

        text = ("привет🙂漢字abc" * 3000) + "🧠"
        pieces = list(utf8_slices(text))
        self.assertGreater(len(pieces), 1)
        self.assertEqual("".join(pieces).encode(), text.encode())
        self.assertTrue(all(0 < len(piece.encode()) <= 8192 for piece in pieces))


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    unittest.main()

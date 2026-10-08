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
                "ZZ_LEAK": "z",
                "MUSE_BIN": "/tmp/evil-muse",
            },
        ):
            out = self.adapter().execute_turn(ctx_for(), None)
        self.assertEqual(out.state, "done")
        env = self.fake.env()
        for name in ("META_API_KEY", "DROID_DSH_BRIDGE_KEY", "ZZ_LEAK", "MUSE_BIN"):
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


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    unittest.main()

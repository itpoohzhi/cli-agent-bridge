"""Проброс сессионного окружения extra_body.env и kill-switch (ADR-0016, Rev A4).

Сценарии идут через настоящий HTTP-сервер моста и fake-subprocess (tests/fake_droid.py):
реальный droid, сеть, браузер и боевые каталоги владельца не используются. Секреты в тестах
фиктивные. Номера O1..O11 — оракулы DoD ADR-0016.
"""

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import server  # noqa: E402
from core import runtime_env  # noqa: E402
from bridge_testlib import pid_alive, wait_until  # noqa: E402
from rpc_testlib import RpcCase  # noqa: E402

CDP = "ws://127.0.0.1:9222/devtools/browser/abc-123"
TOKEN = "gf-NOT-REAL-77"  # короче 24 символов: общий маскировщик токенов его не ловит
PROBE = [
    "AGENT_BROWSER_CDP",
    "GRAFANA_TOKEN",
    "PATH",
    "HOME",
    "SHELL",
    "USER",
    "DYLD_INSERT_LIBRARIES",
    "LD_PRELOAD",
    "PYTHONPATH",
    "NODE_OPTIONS",
    "BASH_ENV",
    "BRIDGE_KEY",
    "DROID_BIN",
    "DROID_AUTO",
    "FACTORY_HOME_OVERRIDE",
    "GOOD_VAR",
]


def env_body(**env):
    return {"env": dict(env)}


class FwdCase(RpcCase):
    """RpcCase + динамический снимок флага GigaRC во временном каталоге."""

    def setUp(self):
        super().setUp()
        self.cfg = Path(self._tmp.name) / "dynamic_config.json"
        patcher = mock.patch.dict(
            os.environ,
            {
                "BRIDGE_DYNAMIC_CONFIG_PATH": str(self.cfg),
                "BRIDGE_CDP_DISCOVERY_PATH": str(Path(self._tmp.name) / "no-devtools"),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(server.FORWARD_FLAG, None)
        self.hub.configure(log_env=PROBE)

    def set_flag(self, value):
        tmp = self.cfg.with_suffix(".tmp")
        tmp.write_text(json.dumps({server.FORWARD_FLAG: value}), encoding="utf-8")
        os.replace(tmp, self.cfg)  # атомарно, новый inode: сигнатура кэша меняется

    def probes(self):
        return [r["probe_env"] for r in self.hub.spawns()]

    def live_pids(self):
        return [r["pid"] for r in self.hub.spawns() if pid_alive(r["pid"])]


class TestForwardingOracles(FwdCase):
    def test_o1_request_env_reaches_child(self):
        """O1: env из extra_body доезжает до дочернего процесса, системные имена не меняются."""
        self.set_flag(True)
        chat = self.conv(
            "c-o1",
            extra_body=env_body(
                AGENT_BROWSER_CDP=CDP, GRAFANA_TOKEN=TOKEN, GOOD_VAR="v1"
            ),
        )
        status, _ = chat.ask("hello")
        self.assertEqual(status, 200)
        probe = self.probes()[0]
        self.assertEqual(probe["AGENT_BROWSER_CDP"], CDP)
        self.assertEqual(probe["GRAFANA_TOKEN"], TOKEN)
        self.assertEqual(probe["GOOD_VAR"], "v1")
        # повторный ход в тот же чат с тем же env — процесс тот же (hot), без перезапуска
        self.assertEqual(chat.ask("again")[0], 200)
        self.assertEqual(len(self.hub.spawns()), 1)

    def test_o2_secret_values_never_in_prompt_or_response_or_stderr(self):
        """O2: значения секретов не попадают в ответ, stderr-диагностику и журнал моста."""
        self.set_flag(True)
        failing = {
            "steps": [
                {"op": "stderr_env", "names": ["GRAFANA_TOKEN", "AGENT_BROWSER_CDP"]},
                {"op": "exit", "rc": 1},
            ]
        }
        self.hub.script([failing] * 3)  # мост делает до 3 попыток
        with self.capture_logs() as lines:
            status, raw = self._post(
                {
                    "model": "claude-sonnet-5-5",
                    "prompt_cache_key": "c-o2",
                    "messages": [{"role": "user", "content": "go"}],
                    "extra_body": env_body(AGENT_BROWSER_CDP=CDP, GRAFANA_TOKEN=TOKEN),
                }
            )
        self.assertNotEqual(
            status, 200
        )  # ход намеренно падает: stderr ребёнка попал в диагностику
        blob = raw + "\n".join(lines)
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn("/devtools/browser/abc-123", blob)
        self.assertIn(
            "forward_env accepted", blob
        )  # мост пробросил и залогировал только маски
        self.assertIn("***", blob)

    def test_o2_negative_control_redaction_is_what_hides_secret(self):
        """O2 (контроль): без вычистки stderr секрет бы утёк — тест O2 не пустой."""
        self.set_flag(True)
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "stderr_env", "names": ["GRAFANA_TOKEN"]},
                        {"op": "exit", "rc": 1},
                    ]
                }
            ]
            * 3
        )
        with mock.patch.object(server, "_redact_values", lambda text, values: text):
            with self.capture_logs() as lines:
                _, raw = self._post(
                    {
                        "model": "claude-sonnet-5-5",
                        "prompt_cache_key": "c-o2n",
                        "messages": [{"role": "user", "content": "go"}],
                        "extra_body": env_body(GRAFANA_TOKEN=TOKEN),
                    }
                )
        self.assertIn(TOKEN, raw + "\n".join(lines))

    def test_o3_denylist_not_overridable_by_request(self):
        """O3: денилист macOS/Linux не подменяется запросом (юнит + через живой spawn)."""
        ambient = mock.patch.dict(os.environ)  # внешний PYTHONPATH родителя не должен влиять на probe
        ambient.start()
        self.addCleanup(ambient.stop)
        os.environ.pop("PYTHONPATH", None)
        evil = {
            "PATH": "/evil/bin",
            "HOME": "/evil/home",
            "SHELL": "/evil/sh",
            "USER": "evil",
            "DYLD_INSERT_LIBRARIES": "/evil/lib.dylib",
            "LD_PRELOAD": "/evil/lib.so",
            "PYTHONPATH": "/evil/py",
            "NODE_OPTIONS": "--require /evil.js",
            "BASH_ENV": "/evil/rc",
            "BRIDGE_KEY": "evil-bridge",
            "DROID_DSH_BRIDGE_KEY": "evil-bridge",
            "MY_BRIDGE_KEY": "evil-bridge",
            "DROID_BIN": "/evil/droid",
            "DROID_AUTO": "high",
            "FACTORY_HOME_OVERRIDE": "/evil/factory",
            "IFS": "x",
            "SSL_CERT_FILE": "/evil.pem",
            "HTTPS_PROXY": "http://evil",
            "BASH_FUNC_x%%": "() { :; }",
            "LD_LIBRARY_PATH": "/evil",
        }
        self.assertEqual(
            server.sanitize_forwarded_env({**evil, "GOOD_VAR": "ok"}),
            {"GOOD_VAR": "ok"},
        )
        self.set_flag(True)
        status, _ = self.conv("c-o3", extra_body=env_body(**evil, GOOD_VAR="ok")).ask(
            "x"
        )
        self.assertEqual(status, 200)
        probe = self.probes()[0]
        self.assertEqual(probe["GOOD_VAR"], "ok")
        for name in (
            "HOME",
            "SHELL",
            "USER",
            "BRIDGE_KEY",
            "DROID_BIN",
            "FACTORY_HOME_OVERRIDE",
        ):
            self.assertNotEqual(probe[name], evil.get(name), name)
        for name in (
            "DYLD_INSERT_LIBRARIES",
            "LD_PRELOAD",
            "PYTHONPATH",
            "NODE_OPTIONS",
            "BASH_ENV",
        ):
            self.assertIsNone(probe[name], name)
        self.assertNotIn("/evil", probe["PATH"])
        self.assertEqual(probe["DROID_AUTO"], "off")

    def test_o3_key_and_value_validation(self):
        """O3: формат ключа и значения (regex, NUL, длина, не-строка)."""
        env = {
            "OK_1": "a",
            "_ok": "b",
            "1BAD": "c",
            "BAD-NAME": "c",
            "BAD=EQ": "c",
            "BAD NAME": "c",
            "A" * 129: "c",
            "A" * 128: "long-key-ok",
            "NUL": "a\0b",
            "BIG": "x" * (server.FORWARD_ENV_MAX_VALUE + 1),
            "EDGE": "x" * server.FORWARD_ENV_MAX_VALUE,
            "NUM": 5,
            "NONE": None,
        }
        out = server.sanitize_forwarded_env(env)
        self.assertEqual(sorted(out), sorted(["OK_1", "_ok", "A" * 128, "EDGE"]))
        self.assertEqual(server.sanitize_forwarded_env(None), {})
        self.assertEqual(server.sanitize_forwarded_env([("A", "b")]), {})

    def test_o4_no_cross_chat_leak(self):
        """O4: секреты чата A не попадают в процесс чата B; A без env — чистый процесс."""
        self.set_flag(True)
        a = self.conv("chat-A", extra_body=env_body(GRAFANA_TOKEN="token-of-A"))
        b = self.conv("chat-B", extra_body=env_body(GRAFANA_TOKEN="token-of-B"))
        self.assertEqual(a.ask("a1")[0], 200)
        self.assertEqual(b.ask("b1")[0], 200)
        pid_a, pid_b = (s["pid"] for s in self.hub.spawns())
        self.assertEqual(
            [p["GRAFANA_TOKEN"] for p in self.probes()], ["token-of-A", "token-of-B"]
        )
        # A продолжает без env: процесс A убит и поднят чистым, процесс B не тронут
        a.extra = {}
        self.assertEqual(a.ask("a2")[0], 200)
        self.assertTrue(wait_until(lambda: not pid_alive(pid_a)))
        self.assertTrue(pid_alive(pid_b))
        spawns = self.hub.spawns()
        self.assertEqual(len(spawns), 3)
        self.assertIsNone(spawns[2]["probe_env"]["GRAFANA_TOKEN"])
        self.assertEqual(self.chat_of("chat-B").env, {"GRAFANA_TOKEN": "token-of-B"})
        self.assertIsNone(self.chat_of("chat-A").env)

    def test_o5_default_off_flag(self):
        """O5: флаг не включён (дефолт false) — extra_body.env игнорируется, PATH прежний."""
        self.assertFalse(server.is_browser_forwarding_enabled())
        status, _ = self.conv("c-o5", extra_body=env_body(GRAFANA_TOKEN=TOKEN)).ask("x")
        self.assertEqual(status, 200)
        probe = self.probes()[0]
        self.assertIsNone(probe["GRAFANA_TOKEN"])
        self.assertNotEqual(self.hub.spawns()[0]["path_head"], str(ROOT / "tools"))
        self.assertIsNone(self.chat_of("c-o5").env)
        # даже мусор в env не даёт 400, пока флаг выключен
        status, _ = self.conv("c-o5b", extra_body={"env": "not-an-object"}).ask("x")
        self.assertEqual(status, 200)
        self.set_flag(False)
        self.assertFalse(server.is_browser_forwarding_enabled())


class TestSessionLifecycle(FwdCase):
    def test_o6_env_change_restarts_process_and_restores_session(self):
        """O6: смена env у живого чата — старый процесс убит, новый с новым env, тот же SID."""
        self.set_flag(True)
        chat = self.conv("c-o6", extra_body=env_body(GRAFANA_TOKEN="first-1"))
        self.assertEqual(chat.ask("q1")[0], 200)
        first = self.chat_of("c-o6")
        pid1, sid = first.proc.pid, first.sid
        chat.extra = {"extra_body": env_body(GRAFANA_TOKEN="second-2")}
        self.assertEqual(chat.ask("q2")[0], 200)
        self.assertTrue(wait_until(lambda: not pid_alive(pid1)))
        self.assertNotEqual(first.proc.pid, pid1)
        self.assertEqual(first.sid, sid)
        self.assertEqual(
            [p["GRAFANA_TOKEN"] for p in self.probes()], ["first-1", "second-2"]
        )
        loads = self.hub.rpcs("droid.load_session")
        self.assertEqual([r["params"]["sessionId"] for r in loads], [sid])

    def test_o7_request_without_env_kills_env_process(self):
        """O7: запрос без env у чата с env — процесс убит, chat.env сброшен, секрета в новом нет."""
        self.set_flag(True)
        chat = self.conv("c-o7", extra_body=env_body(GRAFANA_TOKEN="secret-7"))
        self.assertEqual(chat.ask("q1")[0], 200)
        state = self.chat_of("c-o7")
        pid1 = state.proc.pid
        chat.extra = {"extra_body": {"env": {}}}  # пустой env == отсутствие env
        self.assertEqual(chat.ask("q-next")[0], 200)
        self.assertIsNone(state.env)
        self.assertTrue(wait_until(lambda: not pid_alive(pid1)))
        self.assertIsNone(self.probes()[-1]["GRAFANA_TOKEN"])
        self.assertEqual(len(self.hub.spawns()), 2)
        # следующий ход без env — без лишних перезапусков
        self.assertEqual(chat.ask("q-more")[0], 200)
        self.assertEqual(len(self.hub.spawns()), 2)

    def test_o8_kill_switch_terminates_env_processes_without_restart(self):
        """O8: флаг выключен на лету — процессы с env завершены, чат без env не тронут."""
        self.set_flag(True)
        with_env = self.conv("c-o8a", extra_body=env_body(GRAFANA_TOKEN="secret-8"))
        plain = self.conv("c-o8b")
        self.assertEqual(with_env.ask("q")[0], 200)
        self.assertEqual(plain.ask("q")[0], 200)
        pid_env = self.chat_of("c-o8a").proc.pid
        pid_plain = self.chat_of("c-o8b").proc.pid
        self.assertEqual(
            server._enforce_forward_kill_switch(), 0
        )  # флаг включён — no-op
        self.set_flag(False)  # GigaRC: выключили, мост не перезапускался
        self.assertEqual(server._enforce_forward_kill_switch(), 1)
        self.assertTrue(wait_until(lambda: not pid_alive(pid_env)))
        self.assertTrue(pid_alive(pid_plain))
        self.assertIsNone(self.chat_of("c-o8a").env)
        self.assertIsNone(self.chat_of("c-o8a").proc)
        self.assertEqual(server._enforce_forward_kill_switch(), 0)
        # продолжение чата — новый процесс без секрета
        self.assertEqual(with_env.ask("q2")[0], 200)
        self.assertIsNone(self.probes()[-1]["GRAFANA_TOKEN"])

    def test_o8_kill_switch_fires_on_next_request(self):
        """O8: любой следующий POST при выключенном флаге добивает процессы с env."""
        self.set_flag(True)
        chat = self.conv("c-o8c", extra_body=env_body(GRAFANA_TOKEN="secret-8c"))
        self.assertEqual(chat.ask("q")[0], 200)
        pid = self.chat_of("c-o8c").proc.pid
        os.unlink(self.cfg)  # снимка нет, env-флага нет -> false
        other = self.conv("c-o8d")
        self.assertEqual(other.ask("q")[0], 200)
        self.assertTrue(wait_until(lambda: not pid_alive(pid)))

    def test_o9_zero_disk_leak(self):
        """O9: проброшенные значения не попадают на диск (record чата, state, workspace)."""
        self.set_flag(True)
        chat = self.conv(
            "c-o9", extra_body=env_body(GRAFANA_TOKEN=TOKEN, AGENT_BROWSER_CDP=CDP)
        )
        self.assertEqual(chat.ask("q1")[0], 200)
        self.assertEqual(chat.ask("q2")[0], 200)
        records = list((server._state_dir() / "conversations.v1").rglob("*.json"))
        self.assertTrue(records)
        for record in records:
            self.assertNotIn("env", json.loads(record.read_text(encoding="utf-8")))
        found = []
        for path in server.WORKSPACE.rglob("*"):
            if path.is_file():
                data = path.read_bytes()
                if TOKEN.encode() in data or b"abc-123" in data:
                    found.append(str(path))
        self.assertEqual(found, [])
        self.assertEqual(
            self.chat_of("c-o9").env["GRAFANA_TOKEN"], TOKEN
        )  # только в памяти

    def test_o9_idle_reap_drops_env_from_memory(self):
        """O9: idle-реап и вытеснение стирают env из памяти чата."""
        self.set_flag(True)
        self.assertEqual(
            self.conv("c-o9r", extra_body=env_body(GRAFANA_TOKEN=TOKEN)).ask("q")[0],
            200,
        )
        chat = self.chat_of("c-o9r")
        chat.last_used -= server.IDLE_SECONDS + 1
        self.assertEqual(len(server.REGISTRY.reap_once()), 1)
        self.assertIsNone(chat.env)
        self.assertNotIn(chat.key_hash, server.REGISTRY.env_keys)

    def test_nokey_request_gets_env_in_ephemeral_process(self):
        """Запрос без prompt_cache_key: env уходит в эфемерный процесс, чата в реестре нет."""
        self.set_flag(True)
        status, _ = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "x"}],
                "extra_body": env_body(GRAFANA_TOKEN=TOKEN),
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.probes()[0]["GRAFANA_TOKEN"], TOKEN)


class TestLoopbackAndDiscovery(FwdCase):
    GOOD = [
        "ws://127.0.0.1:9222/devtools/browser/x",
        "wss://localhost:9222/x",
        "http://[::1]:9222",
        "http://127.0.0.1:1024/json",
        "ws://127.0.0.1:65535/",
    ]
    BAD = [
        "ws://127.0.0.1.attacker.invalid:9222/x",
        "ws://evil.example:9222/x",
        "ws://10.0.0.5:9222/x",
        "ws://0.0.0.0:9222/x",
        "ws://127.0.0.1:80/x",
        "ws://127.0.0.1:1023/x",
        "ws://127.0.0.1:65536/x",
        "ws://127.0.0.1/x",
        "ws://127.0.0.1:abc/x",
        "https://127.0.0.1:9222/",
        "ftp://127.0.0.1:9222/",
        "file:///etc/passwd",
        "ws://user:pw@127.0.0.1:9222/",
        "ws://127.0.0.1@evil.example:9222/",
        " ws://127.0.0.1:9222/",
        "ws://127.0.0.1:9222/\nx",
        "",
        "127.0.0.1:9222",
        None,
        9222,
    ]

    def test_o10_is_loopback_cdp_url_table(self):
        for url in self.GOOD:
            self.assertTrue(server.is_loopback_cdp_url(url), url)
        for url in self.BAD:
            self.assertFalse(server.is_loopback_cdp_url(url), repr(url))

    def test_o10_external_cdp_in_request_is_http_400_and_nothing_spawned(self):
        self.set_flag(True)
        for url in (
            "ws://evil.example:9222/x",
            "ws://127.0.0.1.attacker.invalid:9222/x",
            5,
        ):
            status, data = self.conv(
                "c-o10", extra_body=env_body(AGENT_BROWSER_CDP=url)
            ).ask("x")
            self.assertEqual(status, 400, url)
            self.assertEqual(data["error"]["type"], "invalid_request")
        self.assertEqual(self.hub.spawns(), [])
        # не-объект env и чрезмерное число ключей — тоже 400
        status, _ = self.conv("c-o10b", extra_body={"env": ["a"]}).ask("x")
        self.assertEqual(status, 400)
        many = {f"V{i}": "x" for i in range(server.FORWARD_ENV_MAX_KEYS + 1)}
        status, _ = self.conv("c-o10c", extra_body={"env": many}).ask("x")
        self.assertEqual(status, 400)

    def test_o10_discovery_reads_devtools_active_port(self):
        disc = Path(self._tmp.name) / "DevToolsActivePort"
        os.environ["BRIDGE_CDP_DISCOVERY_PATH"] = str(disc)
        disc.write_text("9333\n/devtools/browser/aa-bb-cc\n", encoding="utf-8")
        self.assertEqual(
            server.discover_local_cdp_url(),
            "ws://127.0.0.1:9333/devtools/browser/aa-bb-cc",
        )
        disc.write_text("9333\n", encoding="utf-8")
        self.assertEqual(server.discover_local_cdp_url(), "http://127.0.0.1:9333")
        for bad in (
            "80\n",
            "99999\n",
            "abc\n",
            "",
            "9333\n/devtools/browser/../../x\n",
        ):
            disc.write_text(bad, encoding="utf-8")
            url = server.discover_local_cdp_url()
            self.assertTrue(url is None or url == "http://127.0.0.1:9333", (bad, url))
            self.assertTrue(url is None or "/.." not in url)
        link = Path(self._tmp.name) / "link-port"
        link.symlink_to(disc)
        os.environ["BRIDGE_CDP_DISCOVERY_PATH"] = str(link)
        disc.write_text("9333\n", encoding="utf-8")
        self.assertIsNone(server.discover_local_cdp_url())  # не регулярный файл
        os.environ["BRIDGE_CDP_DISCOVERY_PATH"] = str(Path(self._tmp.name))
        self.assertIsNone(server.discover_local_cdp_url())  # каталог

    def test_o10_discovered_cdp_injected_only_for_opt_in_requests(self):
        disc = Path(self._tmp.name) / "DevToolsActivePort"
        disc.write_text("9444\n/devtools/browser/dd-ee\n", encoding="utf-8")
        os.environ["BRIDGE_CDP_DISCOVERY_PATH"] = str(disc)
        self.set_flag(True)
        self.assertEqual(
            self.conv("c-o10d").ask("x")[0], 200
        )  # без env — ничего не подмешивается
        self.assertIsNone(self.probes()[0]["AGENT_BROWSER_CDP"])
        self.assertEqual(
            self.conv("c-o10e", extra_body=env_body(GOOD_VAR="1")).ask("x")[0], 200
        )
        self.assertEqual(
            self.probes()[1]["AGENT_BROWSER_CDP"],
            "ws://127.0.0.1:9444/devtools/browser/dd-ee",
        )


class TestFlagSourceAndPath(FwdCase):
    def test_o11_flag_cache_is_mtime_based_o1(self):
        """O11: файл перечитывается только при смене сигнатуры; не на каждый вызов."""
        source = server._ForwardFlagSource()
        self.set_flag(True)
        real = runtime_env._load_snapshot
        with mock.patch.object(runtime_env, "_load_snapshot", wraps=real) as load:
            for _ in range(200):
                self.assertTrue(source.enabled())
            self.assertEqual(load.call_count, 1)
            self.set_flag(False)
            for _ in range(200):
                self.assertFalse(source.enabled())
            self.assertEqual(load.call_count, 2)

    def test_o11_flag_precedence_and_fail_closed(self):
        source = server._ForwardFlagSource()
        self.assertFalse(source.enabled())  # нет файла, нет env -> false
        os.environ[server.FORWARD_FLAG] = "true"
        self.assertTrue(source.enabled())  # env-фолбэк
        self.cfg.write_text(json.dumps({"OTHER": 1}), encoding="utf-8")
        self.assertTrue(source.enabled())  # файл без ключа -> env
        self.cfg.write_text(json.dumps({server.FORWARD_FLAG: False}), encoding="utf-8")
        self.assertFalse(source.enabled())  # файл главнее env
        self.cfg.write_text("{broken", encoding="utf-8")
        self.assertFalse(source.enabled())  # повреждён -> fail-closed даже при env=true
        self.cfg.write_text(json.dumps({server.FORWARD_FLAG: "TRUE"}), encoding="utf-8")
        self.assertTrue(source.enabled())

    def test_o11_tools_dir_first_in_path_only_when_enabled(self):
        tools = str(ROOT / "tools")
        self.assertNotEqual(server._launch_env()["PATH"].split(os.pathsep)[0], tools)
        self.set_flag(True)
        parts = server._launch_env()["PATH"].split(os.pathsep)
        self.assertEqual(parts[0], tools)
        self.assertEqual(parts.count(tools), 1)
        self.assertEqual(self.conv("c-o11p").ask("x")[0], 200)
        self.assertEqual(self.hub.spawns()[0]["path_head"], tools)

    def test_log_masking_helpers(self):
        masked = server.mask_env_for_log(
            {
                "GRAFANA_TOKEN": TOKEN,
                "MY_SECRET": "s",
                "api_key": "k",
                "PASSWORD": "p",
                "AUTH_HEADER": "a",
                "AGENT_BROWSER_CDP": CDP,
                "PLAIN": "visible",
            }
        )
        self.assertEqual(masked["PLAIN"], "visible")
        for name in (
            "GRAFANA_TOKEN",
            "MY_SECRET",
            "api_key",
            "PASSWORD",
            "AUTH_HEADER",
            "AGENT_BROWSER_CDP",
        ):
            self.assertEqual(masked[name], "***", name)
        self.assertNotIn("abc-123", server._mask_secrets(f"connect {CDP} failed"))

    def test_concurrent_kill_switch_and_requests_do_not_deadlock(self):
        """Параллельные запросы с env и переключение флага не вешают мост."""
        self.set_flag(True)
        results = []

        def worker(i):
            chat = self.conv(f"c-par-{i}", extra_body=env_body(GRAFANA_TOKEN=f"t-{i}"))
            results.append(chat.ask("x")[0])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(results, [200, 200, 200])
        self.set_flag(False)
        self.assertEqual(server._enforce_forward_kill_switch(), 3)
        self.assertTrue(wait_until(lambda: not self.live_pids()))


class TestReworkCycle1(FwdCase):
    """Доработка по замечаниям Кодового Совета (F-001, F-002, F-005)."""

    FAIL_ONCE = {"steps": [{"op": "exit", "rc": 1}]}

    def test_f001_retry_success_syncs_chat_env(self):
        """F-001: первая попытка упала, retry поднял процесс с env — chat.env == env процесса."""
        self.set_flag(True)
        self.hub.script(
            [self.FAIL_ONCE]
        )  # попытка 1 падает, попытка 2 — сценарий по умолчанию
        chat = self.conv("c-f001", extra_body=env_body(GRAFANA_TOKEN="retry-secret"))
        self.assertEqual(chat.ask("q1")[0], 200)
        state = self.chat_of("c-f001")
        self.assertEqual(len(self.hub.spawns()), 2)
        self.assertEqual(self.probes()[1]["GRAFANA_TOKEN"], "retry-secret")
        self.assertEqual(state.env, {"GRAFANA_TOKEN": "retry-secret"})
        self.assertIn(state.key_hash, server.REGISTRY.env_keys)
        pid = state.proc.pid
        # следующий запрос без env НЕ переиспользует живой процесс с секретом
        chat.extra = {}
        self.assertEqual(chat.ask("q2")[0], 200)
        self.assertTrue(wait_until(lambda: not pid_alive(pid)))
        self.assertNotEqual(state.proc.pid, pid)
        self.assertIsNone(self.probes()[-1]["GRAFANA_TOKEN"])
        self.assertIsNone(state.env)

    def test_f001_kill_switch_at_spawn_drops_env(self):
        """F-001: флаг выключен между приёмом запроса и spawn — env в процесс не передаётся."""
        self.set_flag(True)
        original = server.Handler._forwarded_env

        def accept_then_disable(handler, *args):
            result = original(handler, *args)
            self.set_flag(False)  # kill-switch сработал после приёма env
            return result

        with mock.patch.object(server.Handler, "_forwarded_env", accept_then_disable):
            status, _ = self.conv(
                "c-f001k", extra_body=env_body(GRAFANA_TOKEN=TOKEN)
            ).ask("x")
        self.assertEqual(status, 200)
        self.assertIsNone(self.probes()[0]["GRAFANA_TOKEN"])

    def test_f001_child_env_rechecks_flag(self):
        self.set_flag(False)
        self.assertNotIn("GOOD_VAR", server._child_env({"GOOD_VAR": "v"}))
        self.set_flag(True)
        self.assertEqual(server._child_env({"GOOD_VAR": "v"})["GOOD_VAR"], "v")

    def test_f001_set_chat_env_takes_registry_lock(self):
        """F-001: _set_chat_env сериализован с REGISTRY.lock (нет RuntimeError при итерации)."""
        chat = server.Chat("f" * 64)
        done = threading.Event()

        def call():
            server._set_chat_env(chat, {"A": "b"})
            done.set()

        with server.REGISTRY.lock:
            worker = threading.Thread(target=call)
            worker.start()
            self.assertFalse(done.wait(0.3))  # ждёт замок реестра
        worker.join(timeout=5)
        self.assertTrue(done.is_set())
        self.assertIn(chat.key_hash, server.REGISTRY.env_keys)
        server._set_chat_env(chat, None)
        self.assertNotIn(chat.key_hash, server.REGISTRY.env_keys)

    def test_f001_concurrent_env_updates_and_kill_switch_iteration(self):
        """F-001: параллельные add/discard env_keys и kill-switch не дают RuntimeError."""
        self.set_flag(False)
        chats = [server.Chat(f"{i:064x}") for i in range(50)]
        errors = []
        stop = threading.Event()

        def churn():
            try:
                while not stop.is_set():
                    for chat in chats:
                        server._set_chat_env(chat, {"A": "b"})
                        server._set_chat_env(chat, None)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=churn) for _ in range(3)]
        for t in threads:
            t.start()
        deadline = time.monotonic() + 1.0
        try:
            while time.monotonic() < deadline:
                server._enforce_forward_kill_switch()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            stop.set()
            for t in threads:
                t.join(timeout=5)
            for chat in chats:
                server._set_chat_env(chat, None)
        self.assertEqual(errors, [])

    def test_f002_logs_contain_only_key_names_and_lengths(self):
        """F-002: значения env (в т.ч. не секретные по имени) в журнал не попадают."""
        self.set_flag(True)
        plain = "plain-visible-value-4242"
        with self.capture_logs() as lines:
            status, _ = self.conv(
                "c-f002",
                extra_body=env_body(
                    GRAFANA_TOKEN=TOKEN, AGENT_BROWSER_CDP=CDP, GOOD_VAR=plain
                ),
            ).ask("x")
        self.assertEqual(status, 200)
        blob = "\n".join(lines)
        for value in (TOKEN, plain, "abc-123", CDP):
            self.assertNotIn(value, blob)
        self.assertIn("forward_env accepted", blob)
        self.assertIn(f"('GRAFANA_TOKEN', {len(TOKEN)})", blob)
        self.assertIn(f"('GOOD_VAR', {len(plain)})", blob)

    def test_f002_secret_values_cover_all_values(self):
        out = server._secret_values(
            {"GOOD_VAR": "plain-val", "LONGER": "plain-value-2", "E": ""}
        )
        self.assertEqual(out, ["plain-value-2", "plain-val"])
        self.assertEqual(server._secret_values({}), [])

    def test_f002_non_secret_named_value_redacted_from_child_stderr(self):
        """F-002: значение переменной с «безобидным» именем вычищается из stderr ребёнка."""
        self.set_flag(True)
        plain = "plain-visible-value-4242"
        failing = {
            "steps": [
                {"op": "stderr_env", "names": ["GOOD_VAR"]},
                {"op": "exit", "rc": 1},
            ]
        }
        self.hub.script([failing] * 3)
        with self.capture_logs() as lines:
            status, raw = self._post(
                {
                    "model": "claude-sonnet-5-5",
                    "prompt_cache_key": "c-f002s",
                    "messages": [{"role": "user", "content": "go"}],
                    "extra_body": env_body(GOOD_VAR=plain),
                }
            )
        self.assertNotEqual(status, 200)
        self.assertNotIn(plain, raw + "\n".join(lines))

    def test_f002_passthrough_strips_extra_body_env(self):
        """F-002: extra_body.env не уходит внешнему upstream (тело и разобранный запрос)."""
        req = {
            "model": "m",
            "messages": [],
            "extra_body": {"env": {"GRAFANA_TOKEN": TOKEN}, "cwd": "/x"},
        }
        raw = json.dumps(req).encode()
        new_raw, new_req = server._strip_passthrough_env(raw, req)
        self.assertNotIn(TOKEN.encode(), new_raw)
        self.assertEqual(json.loads(new_raw)["extra_body"], {"cwd": "/x"})
        self.assertEqual(new_req["extra_body"], {"cwd": "/x"})
        self.assertIn("env", req["extra_body"])  # исходный запрос не мутируется
        # без extra_body.env — тело дословно (побайтово)
        plain = b'{"model": "m",  "messages": []}'
        same_raw, same_req = server._strip_passthrough_env(plain, json.loads(plain))
        self.assertIs(same_raw, plain)
        for odd in ({"extra_body": "x"}, {"extra_body": {"cwd": "/x"}}, {}):
            body = json.dumps(odd).encode()
            self.assertIs(server._strip_passthrough_env(body, odd)[0], body)

    def test_f002_serve_passthrough_sends_stripped_body(self):
        req = {"model": "m", "extra_body": {"env": {"GRAFANA_TOKEN": TOKEN}}}
        raw = json.dumps(req).encode()
        adapter = mock.Mock(id="fake")
        fake_self = mock.Mock(path="/v1/chat/completions", headers={"X-A": "b"})
        with mock.patch.object(server, "_HandlerSink"):
            server.Handler._serve_passthrough(fake_self, adapter, raw, req, "m")
        kwargs = adapter.handle.call_args.kwargs
        self.assertNotIn(TOKEN.encode(), kwargs["raw_body"])
        self.assertNotIn("env", kwargs["request"]["extra_body"])

    def test_f005_limits_from_environment(self):
        """F-005: лимиты env-проброса настраиваются, мусор -> безопасные дефолты."""
        self.assertEqual(
            (server.FORWARD_ENV_MAX_KEYS, server.FORWARD_ENV_MAX_VALUE), (64, 32768)
        )
        with mock.patch.dict(os.environ, {"X_LIM": "7"}):
            self.assertEqual(server._env_limit("X_LIM", 64), 7)
        for bad in ("abc", "0", "-3", ""):
            with mock.patch.dict(os.environ, {"X_LIM": bad}):
                self.assertEqual(server._env_limit("X_LIM", 64), 64, bad)
        self.assertEqual(server._env_limit("X_LIM_UNSET_ZZ", 11), 11)
        code = (
            "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r); import server as s; "
            "print(s.FORWARD_ENV_MAX_KEYS, s.FORWARD_ENV_MAX_VALUE)"
            % (str(ROOT), str(ROOT / "tools"))
        )
        env = dict(
            os.environ,
            BRIDGE_FORWARD_ENV_MAX_KEYS="3",
            BRIDGE_FORWARD_ENV_MAX_VALUE="10",
        )
        out = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.split()[-2:], ["3", "10"])

    def test_f005_dynamic_limits_are_enforced(self):
        self.set_flag(True)
        with mock.patch.object(server, "FORWARD_ENV_MAX_KEYS", 2):
            status, data = self.conv(
                "c-f005", extra_body=env_body(A="1", B="2", C="3")
            ).ask("x")
        self.assertEqual(status, 400)
        self.assertIn("at most 2", json.dumps(data))
        with mock.patch.object(server, "FORWARD_ENV_MAX_VALUE", 4):
            self.assertEqual(
                server.sanitize_forwarded_env({"A": "1234", "B": "12345"}),
                {"A": "1234"},
            )


# ---- ADR-0015 / AD-004: canonical и legacy имена не пробрасываются потомку (VER-003) ------
BASE_DENIED_PREFIXES = (
    "DYLD_",
    "LD_",
    "PYTHON",
    "NODE_",
    "BASH_",
    "DROID_",
    "FACTORY_",
    "GIT_",
    "PERL",
    "RUBY",
)
NEW_DENIED_PREFIXES = ("BRIDGE_CLI_", "BRIDGE_NONSTREAM_", "BRIDGE_WATCHDOG_")
# Исчерпывающий список legacy-алиасов из таблиц AD-002/AD-004 (DROID_* семейства).
LEGACY_DROID_ALIASES = (
    "DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S",
    "DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S",
    "DROID_BRIDGE_SILENCE_WATCHDOG_S",
    "DROID_BRIDGE_RPC_CALL_TIMEOUT_S",
    "DROID_DSH_BRIDGE_IDLE_SECONDS",
    "DROID_BRIDGE_MAX_RPC_LINE_BYTES",
    "DROID_BRIDGE_MAX_STDERR_BYTES",
    "DROID_BRIDGE_MAX_INBOX_BYTES",
    "DROID_BRIDGE_MAX_TURN_TEXT_BYTES",
    "DROID_BRIDGE_RUN_QUEUE_MAXSIZE",
    "DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS",
    "DROID_BRIDGE_MAX_DELIVERY_BYTES",
    "DROID_BRIDGE_MAX_CHATS",
    "DROID_DSH_BRIDGE_SAFETY_CAP_S",
    "DROID_LAUNCHER",
    "DROID_BIN",
)
CANONICAL_RUNTIME_NAMES = (
    "BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S",
    "BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S",
    "BRIDGE_CLI_SILENCE_WATCHDOG_S",
    "BRIDGE_CLI_RPC_CALL_TIMEOUT_S",
    "BRIDGE_CLI_IDLE_SECONDS",
    "BRIDGE_CLI_LAUNCHER",
    "BRIDGE_CLI_MAX_RPC_LINE_BYTES",
    "BRIDGE_CLI_MAX_STDERR_BYTES",
    "BRIDGE_CLI_MAX_INBOX_BYTES",
    "BRIDGE_CLI_MAX_TURN_TEXT_BYTES",
    "BRIDGE_CLI_RUN_QUEUE_MAXSIZE",
    "BRIDGE_CLI_MAX_JSON_STRUCT_TOKENS",
    "BRIDGE_CLI_MAX_DELIVERY_BYTES",
    "BRIDGE_CLI_MAX_CHATS",
    "BRIDGE_CLI_NEUTRAL_NAMES_ENABLED",
    "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED",
    "BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S",
    "BRIDGE_NONSTREAM_IDLE_TIMEOUT_S",
    "BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED",
    "BRIDGE_NONSTREAM_SOFT_LIVENESS_BUDGET_S",
    "BRIDGE_NONSTREAM_SOFT_LIVENESS_MIN_CPU_DELTA_S",
    "BRIDGE_NONSTREAM_SAFETY_CAP_S",
    "BRIDGE_NONSTREAM_POLL_INTERVAL_S",
    "BRIDGE_NONSTREAM_TELEMETRY_ENABLED",
    "BRIDGE_WATCHDOG_IDLE_TIMEOUT_S",
    "BRIDGE_WATCHDOG_SAFETY_CAP_S",
    "BRIDGE_WATCHDOG_FINISH_RESERVE_S",
    "BRIDGE_WATCHDOG_INTERVAL_S",
    "BRIDGE_WATCHDOG_PS_TIMEOUT_S",
)


def _case_variants(name: str) -> list[str]:
    """Имя в верхнем, нижнем и «змеином» смешанном регистре."""
    mixed = "".join(c.lower() if i % 2 else c.upper() for i, c in enumerate(name))
    return [name, name.lower(), mixed]


class TestAd004DeniedForwardPrefixes(unittest.TestCase):
    def test_denied_prefixes_contain_new_families(self):
        for prefix in NEW_DENIED_PREFIXES:
            self.assertIn(prefix, server.DENIED_FORWARD_PREFIXES)

    def test_old_denied_prefixes_are_preserved(self):
        for prefix in BASE_DENIED_PREFIXES:
            self.assertIn(prefix, server.DENIED_FORWARD_PREFIXES)
        self.assertEqual(
            set(server.DENIED_FORWARD_PREFIXES),
            set(BASE_DENIED_PREFIXES) | set(NEW_DENIED_PREFIXES),
        )

    def test_old_denied_names_are_preserved(self):
        for name in ("BRIDGE_KEY", "DROID_DSH_BRIDGE_KEY", "DROID_BIN", "DROID_AUTO"):
            self.assertIn(name, server.DENIED_FORWARD_ENV)
        # DROID_BIN по-прежнему закрыт и как имя, и как префикс DROID_
        self.assertEqual(server.sanitize_forwarded_env({"DROID_BIN": "/evil"}), {})

    def test_new_canonical_names_are_dropped_in_any_case(self):
        for name in CANONICAL_RUNTIME_NAMES:
            for variant in _case_variants(name):
                with self.subTest(name=variant):
                    self.assertEqual(
                        server.sanitize_forwarded_env({variant: "1", "GOOD_VAR": "ok"}),
                        {"GOOD_VAR": "ok"},
                    )

    def test_legacy_aliases_are_dropped_in_any_case(self):
        for name in LEGACY_DROID_ALIASES:
            for variant in _case_variants(name):
                with self.subTest(name=variant):
                    self.assertEqual(server.sanitize_forwarded_env({variant: "1"}), {})

    def test_safety_cap_alias_and_canonical_dropped_together(self):
        env = {
            "DROID_DSH_BRIDGE_SAFETY_CAP_S": "1",
            "BRIDGE_WATCHDOG_SAFETY_CAP_S": "1",
            "DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S": "1",
            "BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S": "1",
            "BRIDGE_NONSTREAM_IDLE_TIMEOUT_S": "1",
        }
        self.assertEqual(server.sanitize_forwarded_env(env), {})
        self.assertEqual(
            server.sanitize_forwarded_env({**env, "GOOD_VAR": "ok"}),
            {"GOOD_VAR": "ok"},
        )

    def test_every_name_in_runtime_config_tables_is_denied_or_known_exception(self):
        """Имена из таблиц конфигурации не должны тихо стать пробрасываемыми."""
        from core import cli_runtime_config, liveness_signals

        names = set(cli_runtime_config.LAUNCHER_NAMES)
        specs = [
            *cli_runtime_config._SPECS.values(),
            *cli_runtime_config._NS_SPECS.values(),
            *cli_runtime_config._WD_SPECS.values(),
        ]
        for spec in specs:
            names.update(spec.names)
        names |= {
            liveness_signals.FLAG_VIA_STREAM,
            liveness_signals.FLAG_SOFT_LIVENESS,
            liveness_signals.FLAG_TELEMETRY,
            cli_runtime_config.FLAG_NEUTRAL_NAMES,
        }
        # Без префикса семейств: читаются только самим мостом, потомку не нужны.
        bridge_only = {"BRIDGE_IDLE_TIMEOUT_S", "BRIDGE_PASSTHROUGH_POLL_INTERVAL_S"}
        self.assertTrue(set(CANONICAL_RUNTIME_NAMES) <= names)
        self.assertTrue(set(LEGACY_DROID_ALIASES) - {"DROID_BIN"} <= names)
        for name in sorted(names - bridge_only):
            with self.subTest(name=name):
                self.assertEqual(server.sanitize_forwarded_env({name: "1"}), {})

    def test_harmless_names_still_pass(self):
        env = {
            "GOOD_VAR": "ok",
            "MY_BRIDGE_SETTING": "1",  # не начинается с BRIDGE_CLI_/NONSTREAM_/WATCHDOG_
            "CLI_BRIDGE_X": "2",
            "NONSTREAM_FLAG": "3",
            "WATCHDOG_X": "4",
            "XBRIDGE_CLI_X": "5",
        }
        self.assertEqual(server.sanitize_forwarded_env(env), env)

    def test_prefix_match_is_by_prefix_not_substring(self):
        self.assertEqual(
            server.sanitize_forwarded_env({"BRIDGE_CLI_": "1", "BRIDGE_WATCHDOG_": "1"}),
            {},
        )
        self.assertEqual(
            server.sanitize_forwarded_env({"BRIDGE_CLIENT_X": "1"}),
            {"BRIDGE_CLIENT_X": "1"},
        )


class TestAd004FlagSourceHierarchy(unittest.TestCase):
    def test_forward_flag_source_extends_shared_dynamic_flag_source(self):
        from core.runtime_env import DynamicFlagSource

        self.assertTrue(issubclass(server._ForwardFlagSource, DynamicFlagSource))
        self.assertTrue(issubclass(server._PassthroughAuthFlagSource, DynamicFlagSource))
        self.assertTrue(
            issubclass(server._PassthroughAuthFlagSource, server._ForwardFlagSource)
        )

    def test_flag_names_are_unchanged(self):
        self.assertEqual(
            server._ForwardFlagSource._flag_name, "BRIDGE_BROWSER_FORWARDING_ENABLED"
        )
        self.assertEqual(
            server._PassthroughAuthFlagSource._flag_name,
            "BRIDGE_PASSTHROUGH_UPSTREAM_KEY_AUTH_ENABLED",
        )
        self.assertEqual(server._ForwardFlagSource._flag_name, server.FORWARD_FLAG)
        self.assertEqual(
            server._PassthroughAuthFlagSource._flag_name, server.PASSTHROUGH_AUTH_FLAG
        )
        self.assertEqual(server._FORWARD_FLAG_SOURCE._flag_name, server.FORWARD_FLAG)
        self.assertEqual(
            server.PASSTHROUGH_AUTH_FLAG_SOURCE._flag_name, server.PASSTHROUGH_AUTH_FLAG
        )

    def test_subclasses_do_not_share_state_or_flag_names(self):
        forward = server._ForwardFlagSource()
        passthrough = server._PassthroughAuthFlagSource()
        self.assertNotEqual(forward._flag_name, passthrough._flag_name)  # общий снимок файла, разные ключи
        self.assertIsInstance(forward, runtime_env.DynamicFlagSource)
        self.assertIsInstance(passthrough, runtime_env.DynamicFlagSource)

    def test_default_false_snapshot_override_and_fail_closed(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            cfg = Path(directory) / "dynamic_config.json"
            with mock.patch.dict(
                os.environ, {"BRIDGE_DYNAMIC_CONFIG_PATH": str(cfg)}, clear=False
            ):
                os.environ.pop(server.FORWARD_FLAG, None)
                os.environ.pop(server.PASSTHROUGH_AUTH_FLAG, None)
                forward = server._ForwardFlagSource()
                passthrough = server._PassthroughAuthFlagSource()
                self.assertFalse(forward.enabled())
                self.assertFalse(passthrough.enabled())
                cfg.write_text(
                    json.dumps({server.FORWARD_FLAG: True}), encoding="utf-8"
                )
                self.assertTrue(forward.enabled())
                self.assertFalse(passthrough.enabled())  # свой ключ, чужой не действует
                cfg.write_text("{broken", encoding="utf-8")
                self.assertFalse(forward.enabled())
                self.assertFalse(passthrough.enabled())


class TestAd004DeniedNamesNeverReachChild(FwdCase):
    """Сквозная проверка: имена семейств не доезжают до реального дочернего процесса."""

    NAMES = (
        "BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S",
        "BRIDGE_NONSTREAM_IDLE_TIMEOUT_S",
        "BRIDGE_WATCHDOG_SAFETY_CAP_S",
        "DROID_BRIDGE_MAX_CHATS",
        "DROID_DSH_BRIDGE_SAFETY_CAP_S",
        "DROID_DSH_BRIDGE_IDLE_SECONDS",
    )

    def test_denied_runtime_names_do_not_reach_child_process(self):
        self.hub.configure(log_env=[*PROBE, *self.NAMES])
        self.set_flag(True)
        evil = {name: "777" for name in self.NAMES}
        status, _ = self.conv(
            "c-ad004", extra_body=env_body(**evil, GOOD_VAR="ok")
        ).ask("hello")
        self.assertEqual(status, 200)
        probe = self.probes()[0]
        self.assertEqual(probe["GOOD_VAR"], "ok")
        for name in self.NAMES:
            self.assertNotEqual(probe[name], "777", name)


if __name__ == "__main__":
    unittest.main()

"""Тесты окружения потомка `droid exec`: что доезжает, что вырезается.

Проверяется контракт `_launch_env()`: FACTORY_API_KEY (headless-вход Droid)
сохраняется, авторизационные ключи моста (BRIDGE_KEY, DROID_DSH_BRIDGE_KEY, любые
`*_BRIDGE_KEY` и `BRIDGE_*KEY*`) вырезаются (ADR 0015, BLOCKER-SAFETY B1).
Сеть и droid не вызываются; значения ключей в тесте фиктивные.
"""

import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import server  # noqa: E402
from bridge_testlib import BridgeCase  # noqa: E402
from core.cli_runtime_config import (  # noqa: E402
    CliRuntimeConfig,
    cli_number,
    neutral_names_enabled,
)
from core.runtime_env import ConfigError  # noqa: E402
from rpc_testlib import RpcCase  # noqa: E402
from core.backend_adapter import is_bridge_secret_name, strip_bridge_secrets  # noqa: E402
from core.turn_session_manager import mask_secrets  # noqa: E402
from tools import droid_image  # noqa: E402

FAKE_FACTORY_KEY = "fk-TEST-NOT-REAL"
FAKE_BRIDGE_KEY = "bridge-test-key-not-real"


class TestLaunchEnv(unittest.TestCase):
    """`_launch_env()` как единственная точка формирования окружения потомка."""

    def setUp(self):
        self._env = {
            k: os.environ.get(k) for k in ("FACTORY_API_KEY", "DROID_DSH_BRIDGE_KEY")
        }

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_factory_key_survives_and_bridge_key_is_dropped(self):
        os.environ["FACTORY_API_KEY"] = FAKE_FACTORY_KEY
        os.environ["DROID_DSH_BRIDGE_KEY"] = FAKE_BRIDGE_KEY
        env = server._launch_env()
        self.assertEqual(env.get("FACTORY_API_KEY"), FAKE_FACTORY_KEY)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
        # Ключ моста не утёк под другим именем
        self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))

    def test_bridge_key_is_dropped(self):
        """ADR 0015 B1: новое имя ключа хаба `BRIDGE_KEY` тоже не доезжает до потомка."""
        os.environ["BRIDGE_KEY"] = FAKE_BRIDGE_KEY
        try:
            env = server._launch_env()
        finally:
            os.environ.pop("BRIDGE_KEY", None)
        self.assertNotIn("BRIDGE_KEY", env)
        self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))

    def test_both_bridge_key_names_dropped_together(self):
        with mock.patch.dict(
            os.environ,
            {
                "BRIDGE_KEY": FAKE_BRIDGE_KEY,
                "DROID_DSH_BRIDGE_KEY": FAKE_BRIDGE_KEY + "-legacy",
                "FACTORY_API_KEY": FAKE_FACTORY_KEY,
            },
        ):
            env = server._launch_env()
        self.assertNotIn("BRIDGE_KEY", env)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
        self.assertEqual(env.get("FACTORY_API_KEY"), FAKE_FACTORY_KEY)
        leaked = {FAKE_BRIDGE_KEY, FAKE_BRIDGE_KEY + "-legacy"} & set(env.values())
        self.assertEqual(leaked, set())

    def test_suffix_and_pattern_bridge_keys_dropped_ordinary_survive(self):
        secrets = {
            "MUSE_BRIDGE_KEY": "s1",
            "AGY_BRIDGE_KEY": "s2",
            "BRIDGE_API_KEY": "s3",
            "BRIDGE_AUTH_KEY_2": "s4",
            "droid_dsh_bridge_key": "s5",
        }
        ordinary = {
            "BRIDGE_HOST": "127.0.0.1",
            "BRIDGE_PORT": "9882",
            "BRIDGE_INSTR_LIMIT": "100000",
            "DROID_DSH_BRIDGE_HOST": "127.0.0.1",
            "KEYCHAIN_NAME": "login",
            "PATH": "/usr/bin",
        }
        with mock.patch.dict(os.environ, {**secrets, **ordinary}), mock.patch.object(
            server, "is_browser_forwarding_enabled", return_value=True
        ):
            env = server._launch_env()
        for name in secrets:
            self.assertNotIn(name, env, name)
        ordinary["PATH"] = f"{server.ROOT / 'tools'}{os.pathsep}{ordinary['PATH']}"
        for name, value in ordinary.items():
            self.assertEqual(env.get(name), value, name)

    def test_child_env_has_no_bridge_keys(self):
        """`_child_env()` строится поверх `_launch_env()`: ключи моста не попадают и в окружение droid-ребёнка."""
        with mock.patch.dict(
            os.environ,
            {"BRIDGE_KEY": FAKE_BRIDGE_KEY, "DROID_DSH_BRIDGE_KEY": FAKE_BRIDGE_KEY},
        ), mock.patch.object(server, "_mkdir_private"), mock.patch.object(
            server, "_droid_image", return_value=None
        ):
            env = server._child_env()
        self.assertFalse([n for n in env if is_bridge_secret_name(n)], sorted(env))
        self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))

    def test_strip_bridge_secrets_in_place_and_returns_same_dict(self):
        env = {"BRIDGE_KEY": "a", "X_BRIDGE_KEY": "b", "HOME": "/h"}
        self.assertIs(strip_bridge_secrets(env), env)
        self.assertEqual(env, {"HOME": "/h"})

    def test_absent_factory_key_does_not_appear(self):
        os.environ.pop("FACTORY_API_KEY", None)
        env = server._launch_env()
        self.assertNotIn("FACTORY_API_KEY", env)

    def test_bridge_env_cascade(self):
        """HOST/PORT/KEY: BRIDGE_* -> DROID_DSH_BRIDGE_* -> умолчание; пустое значение = не задано."""
        names = (
            "BRIDGE_HOST",
            "DROID_DSH_BRIDGE_HOST",
        )
        with mock.patch.dict(os.environ, {}, clear=False):
            for name in names:
                os.environ.pop(name, None)
            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "127.0.0.1")
            os.environ["DROID_DSH_BRIDGE_HOST"] = "10.0.0.2"
            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "10.0.0.2")
            os.environ["BRIDGE_HOST"] = "10.0.0.3"
            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "10.0.0.3")
            os.environ["BRIDGE_HOST"] = "  "
            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "10.0.0.2")

    def test_bridge_env_accepts_full_canonical_name(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server._bridge_env("BRIDGE_KEY", "default"), "default")
            os.environ["DROID_DSH_BRIDGE_KEY"] = "legacy-key"
            self.assertEqual(server._bridge_env("BRIDGE_KEY"), "legacy-key")
            os.environ["BRIDGE_KEY"] = "canonical-key"
            self.assertEqual(server._bridge_env("BRIDGE_KEY"), "canonical-key")

    def test_bridge_env_full_name_empty_value_falls_back_to_legacy(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"BRIDGE_KEY": "", "DROID_DSH_BRIDGE_KEY": "legacy-key"},
            clear=True,
        ):
            self.assertEqual(server._bridge_env("BRIDGE_KEY", "default"), "legacy-key")
            os.environ.pop("DROID_DSH_BRIDGE_KEY")
            self.assertEqual(server._bridge_env("BRIDGE_KEY", "default"), "default")

    def test_snapshot_masking_covers_bridge_key_assignment_without_env(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            for name in ("BRIDGE_KEY", "DROID_DSH_BRIDGE_KEY", "bridge_key"):
                for separator in ("=", ": "):
                    with self.subTest(name=name, separator=separator):
                        self.assertEqual(
                            mask_secrets(f"{name}{separator}{FAKE_BRIDGE_KEY}"),
                            f"{name}{separator}[REDACTED]",
                        )

    def test_snapshot_masking_covers_bridge_key_value_from_env(self) -> None:
        with mock.patch.dict(os.environ, {"BRIDGE_KEY": FAKE_BRIDGE_KEY}, clear=True):
            self.assertEqual(
                mask_secrets("diagnostic: " + FAKE_BRIDGE_KEY),
                "diagnostic: [REDACTED]",
            )

    def test_image_probe_child_env_drops_both_bridge_keys(self) -> None:
        with (
            mock.patch.dict(
                os.environ,
                {
                    "BRIDGE_KEY": FAKE_BRIDGE_KEY,
                    "DROID_DSH_BRIDGE_KEY": "legacy-test-key",
                    "FACTORY_API_KEY": FAKE_FACTORY_KEY,
                },
                clear=True,
            ),
            mock.patch.object(droid_image.subprocess, "Popen") as popen,
            mock.patch.object(droid_image.threading.Thread, "start"),
        ):
            droid_image._Rpc(Path("/fake/image"), Path("/fake/cwd"), Path("/fake/home"))
        child_env = popen.call_args.kwargs["env"]
        self.assertNotIn("BRIDGE_KEY", child_env)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", child_env)
        self.assertEqual(child_env["FACTORY_API_KEY"], FAKE_FACTORY_KEY)

    def test_masking_covers_short_factory_key(self):
        masked = server._mask_secrets("auth: " + FAKE_FACTORY_KEY)
        self.assertNotIn(FAKE_FACTORY_KEY, masked)
        self.assertIn("***", masked)

    def test_masking_leaves_ordinary_text_intact(self):
        plain = "no secrets here at all"
        self.assertEqual(server._mask_secrets(plain), plain)


# ---- ADR-0015 / AD-004: универсальные имена CLI-раннера на уровне server (VER-003) ---------
CLI_ENV_TABLE = (
    # (поле CliRuntimeConfig, canonical ENV, legacy ENV, default, low, high)
    ("first_token_timeout_s", "BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S", "DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S", 90.0, 1, 3600),
    ("live_write_timeout_s", "BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", "DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", 30.0, 1, 300),
    ("silence_watchdog_s", "BRIDGE_CLI_SILENCE_WATCHDOG_S", "DROID_BRIDGE_SILENCE_WATCHDOG_S", 120.0, 1, 3600),
    ("rpc_call_timeout_s", "BRIDGE_CLI_RPC_CALL_TIMEOUT_S", "DROID_BRIDGE_RPC_CALL_TIMEOUT_S", 60.0, 1, 3600),
    ("idle_seconds", "BRIDGE_CLI_IDLE_SECONDS", "DROID_DSH_BRIDGE_IDLE_SECONDS", 2700.0, 1, 86400),
    ("max_rpc_line_bytes", "BRIDGE_CLI_MAX_RPC_LINE_BYTES", "DROID_BRIDGE_MAX_RPC_LINE_BYTES", 8388608, 1024, 268435456),
    ("max_stderr_bytes", "BRIDGE_CLI_MAX_STDERR_BYTES", "DROID_BRIDGE_MAX_STDERR_BYTES", 65536, 1024, 16777216),
    ("max_inbox_bytes", "BRIDGE_CLI_MAX_INBOX_BYTES", "DROID_BRIDGE_MAX_INBOX_BYTES", 4194304, 1024, 268435456),
    ("max_turn_text_bytes", "BRIDGE_CLI_MAX_TURN_TEXT_BYTES", "DROID_BRIDGE_MAX_TURN_TEXT_BYTES", 10485760, 1024, 1073741824),
    ("run_queue_maxsize", "BRIDGE_CLI_RUN_QUEUE_MAXSIZE", "DROID_BRIDGE_RUN_QUEUE_MAXSIZE", 1024, 1, 65536),
    ("max_json_struct_tokens", "BRIDGE_CLI_MAX_JSON_STRUCT_TOKENS", "DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS", 50000, 1, 10000000),
    ("max_delivery_bytes", "BRIDGE_CLI_MAX_DELIVERY_BYTES", "DROID_BRIDGE_MAX_DELIVERY_BYTES", 268435456, 1048576, 4294967296),
    ("max_chats", "BRIDGE_CLI_MAX_CHATS", "DROID_BRIDGE_MAX_CHATS", 4096, 1, 65536),
)
# Поле CliRuntimeConfig -> константа модуля server, собранная из CLI_CFG.
SERVER_CONSTANTS = {
    "first_token_timeout_s": "FIRST_TOKEN_TIMEOUT_S",
    "live_write_timeout_s": "LIVE_WRITE_TIMEOUT_S",
    "silence_watchdog_s": "SILENCE_WATCHDOG_S",
    "rpc_call_timeout_s": "RPC_CALL_TIMEOUT_S",
    "idle_seconds": "IDLE_SECONDS",
    "max_rpc_line_bytes": "MAX_RPC_LINE_BYTES",
    "max_stderr_bytes": "MAX_STDERR_BYTES",
    "max_inbox_bytes": "MAX_INBOX_BYTES",
    "max_turn_text_bytes": "MAX_TURN_TEXT_BYTES",
    "run_queue_maxsize": "RUN_QUEUE_MAXSIZE",
    "max_json_struct_tokens": "MAX_JSON_STRUCT_TOKENS",
    "max_delivery_bytes": "MAX_DELIVERY_BYTES",
    "max_chats": "MAX_CHATS",
}
NEUTRAL_FLAG = "BRIDGE_CLI_NEUTRAL_NAMES_ENABLED"
HEALTH_KEYS = frozenset(
    {"ok", "transport", "model", "active", "max_concurrent", "tool_emulation", "uptime_s"}
)
ALL_CLI_ENV_NAMES = tuple(
    name for _f, canonical, legacy, *_r in CLI_ENV_TABLE for name in (canonical, legacy)
) + ("BRIDGE_CLI_LAUNCHER", "DROID_LAUNCHER", NEUTRAL_FLAG)
BEHAVIOR_FLAGS = (
    NEUTRAL_FLAG,
    "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED",
    "BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED",
    "BRIDGE_NONSTREAM_TELEMETRY_ENABLED",
)
LABELS = {
    "exec": ("droid exec", "cli-exec"),
    "no_event": ("no droid event", "no CLI event"),
    "no_progress": ("no droid progress", "no CLI progress"),
    "completion_prefix": ("chatcmpl-droid-", "chatcmpl-cli-"),
    "bridge": ("droid-bridge", "cli-agent-bridge"),
}


class _FlagEnvMixin:
    """Динамические флаги читаются из env; реальный ~/.config на тест не влияет."""

    def isolate_flags(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dyn_cfg = Path(tmp.name) / "absent-dynamic-config.json"
        patcher = mock.patch.dict(
            os.environ, {"BRIDGE_DYNAMIC_CONFIG_PATH": str(self.dyn_cfg)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in (*BEHAVIOR_FLAGS, *ALL_CLI_ENV_NAMES):
            os.environ.pop(name, None)


class TestCliRuntimeConfigAliasCascade(unittest.TestCase):
    def test_defaults_match_adr_table(self):
        cfg = CliRuntimeConfig.from_env({})
        for field, _canon, _legacy, default, _lo, _hi in CLI_ENV_TABLE:
            with self.subTest(field=field):
                self.assertEqual(getattr(cfg, field), default)
                self.assertIs(type(getattr(cfg, field)), type(default))
        self.assertEqual(cfg.launcher, "")

    def test_canonical_then_legacy_then_default(self):
        for field, canonical, legacy, default, low, _hi in CLI_ENV_TABLE:
            first, second = low + 1, low + 2
            kind = type(default)
            with self.subTest(field=field):
                self.assertEqual(
                    getattr(CliRuntimeConfig.from_env({legacy: str(second)}), field),
                    kind(second),
                )
                self.assertEqual(
                    getattr(CliRuntimeConfig.from_env({canonical: str(first)}), field),
                    kind(first),
                )
                both = {canonical: str(first), legacy: str(second)}
                self.assertEqual(getattr(CliRuntimeConfig.from_env(both), field), kind(first))

    def test_empty_canonical_yields_to_legacy_and_both_empty_to_default(self):
        for field, canonical, legacy, default, low, _hi in CLI_ENV_TABLE:
            with self.subTest(field=field):
                cfg = CliRuntimeConfig.from_env({canonical: "  ", legacy: str(low + 2)})
                self.assertEqual(getattr(cfg, field), type(default)(low + 2))
                cfg = CliRuntimeConfig.from_env({canonical: "", legacy: " "})
                self.assertEqual(getattr(cfg, field), default)

    def test_bounds_are_inclusive_and_violations_fail_fast_with_neutral_name(self):
        for field, canonical, _legacy, default, low, high in CLI_ENV_TABLE:
            kind = type(default)
            with self.subTest(field=field, edge="valid"):
                self.assertEqual(
                    getattr(CliRuntimeConfig.from_env({canonical: str(low)}), field), kind(low)
                )
                self.assertEqual(
                    getattr(CliRuntimeConfig.from_env({canonical: str(high)}), field), kind(high)
                )
            for bad in (str(low - 1), str(high + 1), "abc", "nan", "inf"):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ConfigError) as ctx:
                        CliRuntimeConfig.from_env({canonical: bad})
                    self.assertEqual(
                        str(ctx.exception), "invalid config parameter: " + canonical
                    )

    def test_invalid_legacy_value_names_canonical_parameter_not_value(self):
        secret_like = "LEAK-NOT-REAL-999"
        with self.assertRaises(ConfigError) as ctx:
            CliRuntimeConfig.from_env({"DROID_BRIDGE_MAX_CHATS": secret_like})
        self.assertIn("BRIDGE_CLI_MAX_CHATS", str(ctx.exception))
        self.assertNotIn(secret_like, str(ctx.exception))

    def test_integer_fields_reject_fractions_float_fields_accept_them(self):
        with self.assertRaises(ConfigError):
            CliRuntimeConfig.from_env({"BRIDGE_CLI_MAX_CHATS": "1.5"})
        cfg = CliRuntimeConfig.from_env({"BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S": "1.5"})
        self.assertEqual(cfg.first_token_timeout_s, 1.5)

    def test_droid_launcher_sets_launcher_and_canonical_wins(self):
        self.assertEqual(
            CliRuntimeConfig.from_env({"DROID_LAUNCHER": "/opt/legacy.sh"}).launcher,
            "/opt/legacy.sh",
        )
        both = {"BRIDGE_CLI_LAUNCHER": "/opt/new.sh", "DROID_LAUNCHER": "/opt/legacy.sh"}
        self.assertEqual(CliRuntimeConfig.from_env(both).launcher, "/opt/new.sh")
        empty = {"BRIDGE_CLI_LAUNCHER": " ", "DROID_LAUNCHER": "/opt/legacy.sh"}
        self.assertEqual(CliRuntimeConfig.from_env(empty).launcher, "/opt/legacy.sh")

    def test_droid_bin_does_not_replace_launcher(self):
        cfg = CliRuntimeConfig.from_env({"DROID_BIN": "/opt/vendor/droid"})
        self.assertEqual(cfg.launcher, "")
        both = CliRuntimeConfig.from_env(
            {"DROID_BIN": "/opt/vendor/droid", "DROID_LAUNCHER": "/opt/l.sh"}
        )
        self.assertEqual(both.launcher, "/opt/l.sh")
        self.assertIn("DROID_BIN", server.DENIED_FORWARD_ENV)

    def test_config_is_immutable(self):
        cfg = CliRuntimeConfig.from_env({})
        with self.assertRaises(dataclasses.FrozenInstanceError):
            cfg.max_chats = 1  # type: ignore[misc]

    def test_from_env_reads_process_environment_by_default(self):
        with mock.patch.dict(os.environ, {"BRIDGE_CLI_MAX_CHATS": "7"}):
            self.assertEqual(CliRuntimeConfig.from_env().max_chats, 7)

    def test_cli_number_is_fail_fast_on_bad_value(self):
        with mock.patch.dict(os.environ, {"BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S": "9999"}):
            with self.assertRaises(ConfigError):
                cli_number("live_write_timeout_s", 30.0)
            with self.assertRaises(ConfigError):
                server.parse_live_write_timeout(30.0)
        with mock.patch.dict(os.environ, {"DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S": "12"}):
            self.assertEqual(cli_number("live_write_timeout_s", 30.0), 12.0)
        with mock.patch.dict(os.environ, {}):
            for name in ("BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", "DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S"):
                os.environ.pop(name, None)
            self.assertEqual(server.parse_live_write_timeout(25.0), 25.0)


class TestServerCliConfigWiring(unittest.TestCase):
    def test_cli_cfg_is_cli_runtime_config(self):
        self.assertIsInstance(server.CLI_CFG, CliRuntimeConfig)

    def test_server_constants_come_from_cli_cfg(self):
        for field, name in SERVER_CONSTANTS.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(server, name), getattr(server.CLI_CFG, field))

    def test_launcher_follows_cli_cfg_or_default_policy(self):
        default = str(Path.home() / ".config" / "factory-launch" / "droid-cli.sh")
        self.assertEqual(server.LAUNCHER, server.CLI_CFG.launcher or default)

    @staticmethod
    def _import_server(extra_env: dict[str, str]):
        code = (
            "import json, sys; sys.path.insert(0, %r); sys.path.insert(0, %r); import server as s; "
            "print(json.dumps({'launcher': s.LAUNCHER, 'chats': s.MAX_CHATS, "
            "'first': s.FIRST_TOKEN_TIMEOUT_S, 'idle': s.IDLE_SECONDS, "
            "'cfg_launcher': s.CLI_CFG.launcher}))" % (str(ROOT), str(ROOT / "tools"))
        )
        env = {k: v for k, v in os.environ.items() if k not in ALL_CLI_ENV_NAMES}
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )

    def test_composition_root_applies_canonical_legacy_and_launcher_names(self):
        run = self._import_server(
            {
                "DROID_BRIDGE_MAX_CHATS": "11",
                "BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S": "33",
                "DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S": "44",
                "DROID_DSH_BRIDGE_IDLE_SECONDS": "55",
                "DROID_LAUNCHER": "/opt/legacy-launcher.sh",
                "DROID_BIN": "/opt/vendor/droid",
            }
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        data = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(
            (data["chats"], data["first"], data["idle"]), (11, 33.0, 55.0)
        )
        self.assertEqual(data["launcher"], "/opt/legacy-launcher.sh")

    def test_droid_bin_alone_does_not_become_launcher(self):
        run = self._import_server({"DROID_BIN": "/opt/vendor/droid"})
        self.assertEqual(run.returncode, 0, run.stderr)
        data = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(data["cfg_launcher"], "")
        self.assertNotEqual(data["launcher"], "/opt/vendor/droid")
        self.assertTrue(data["launcher"].endswith("droid-cli.sh"))

    def test_canonical_launcher_beats_legacy_launcher(self):
        run = self._import_server(
            {"BRIDGE_CLI_LAUNCHER": "/opt/new.sh", "DROID_LAUNCHER": "/opt/old.sh"}
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout.strip().splitlines()[-1])["launcher"], "/opt/new.sh")

    def test_invalid_number_fails_fast_at_start_without_echoing_value(self):
        bad = "LEAK-NOT-REAL-424242"
        run = self._import_server({"BRIDGE_CLI_MAX_CHATS": bad})
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("BRIDGE_CLI_MAX_CHATS", run.stderr)
        self.assertNotIn(bad, run.stderr)


class TestLaunchEnvWithRuntimeFlags(_FlagEnvMixin, unittest.TestCase):
    """`_launch_env()` не меняет контракт ни при одном флаге ADR-0015."""

    def setUp(self):
        self.isolate_flags()

    def test_bridge_keys_dropped_and_factory_key_kept_under_all_flags(self):
        env_in = {
            "BRIDGE_KEY": FAKE_BRIDGE_KEY,
            "DROID_DSH_BRIDGE_KEY": FAKE_BRIDGE_KEY + "-legacy",
            "FACTORY_API_KEY": FAKE_FACTORY_KEY,
            **{flag: "true" for flag in BEHAVIOR_FLAGS},
        }
        with mock.patch.dict(os.environ, env_in):
            env = server._launch_env()
        self.assertNotIn("BRIDGE_KEY", env)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
        self.assertEqual(env.get("FACTORY_API_KEY"), FAKE_FACTORY_KEY)
        self.assertEqual(
            {FAKE_BRIDGE_KEY, FAKE_BRIDGE_KEY + "-legacy"} & set(env.values()), set()
        )

    def test_vendor_variables_are_still_not_taken_from_runtime_config_names(self):
        with mock.patch.dict(os.environ, {"DROID_BIN": "/opt/vendor/droid"}):
            self.assertEqual(
                CliRuntimeConfig.from_env(dict(os.environ)).launcher, ""
            )
            self.assertIn("DROID_BIN", server.DENIED_FORWARD_ENV)
            self.assertEqual(server.sanitize_forwarded_env({"DROID_BIN": "/x"}), {})


class TestNeutralNames(_FlagEnvMixin, unittest.TestCase):
    def setUp(self):
        self.isolate_flags()

    def test_default_labels_are_vendor_strings(self):
        self.assertFalse(neutral_names_enabled())
        for key, (legacy, _neutral) in LABELS.items():
            with self.subTest(key=key):
                self.assertEqual(server.cli_label(key), legacy)
        self.assertEqual(server.cli_label("completion_prefix"), "chatcmpl-droid-")

    def test_flag_true_switches_all_labels_without_restart(self):
        with mock.patch.dict(os.environ, {NEUTRAL_FLAG: "true"}):
            for key, (_legacy, neutral) in LABELS.items():
                with self.subTest(key=key):
                    self.assertEqual(server.cli_label(key), neutral)
            self.assertEqual(server.cli_label("completion_prefix"), "chatcmpl-cli-")
        self.assertEqual(server.cli_label("completion_prefix"), "chatcmpl-droid-")

    def test_flag_values_and_dynamic_snapshot_kill_switch(self):
        for raw, expected in (("1", True), ("yes", True), ("on", True), ("false", False), ("0", False), ("junk", False), ("", False)):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {NEUTRAL_FLAG: raw}):
                self.assertEqual(neutral_names_enabled(), expected)
        with mock.patch.dict(os.environ, {NEUTRAL_FLAG: "true"}):
            self.dyn_cfg.write_text(json.dumps({NEUTRAL_FLAG: False}), encoding="utf-8")
            self.assertEqual(server.cli_label("exec"), "droid exec")  # файл главнее env
            replacement = self.dyn_cfg.with_suffix(".new")
            replacement.write_text(json.dumps({NEUTRAL_FLAG: True}), encoding="utf-8")
            os.replace(replacement, self.dyn_cfg)
            self.assertEqual(server.cli_label("exec"), "cli-exec")  # без рестарта
            self.dyn_cfg.write_text("{broken", encoding="utf-8")
            self.assertEqual(server.cli_label("exec"), "droid exec")  # fail-closed

    def test_droid_error_type_is_kept_message_is_neutral_only_under_flag(self):
        out = {"state": "droid_error", "err": "x"}
        body = server.Handler._error_body(out)
        self.assertEqual((body["type"], body["code"], body["message"]), ("droid_error", 502, "x"))
        silent = {"state": "droid_error"}
        legacy = server.Handler._error_body(silent)
        self.assertEqual(legacy["type"], "droid_error")
        self.assertEqual(legacy["message"], "droid exec reported an error")
        with mock.patch.dict(os.environ, {NEUTRAL_FLAG: "true"}):
            neutral = server.Handler._error_body(silent)
            with_err = server.Handler._error_body(out)
        self.assertEqual(neutral["type"], "droid_error")  # вендорский контракт не переименован
        self.assertEqual(neutral["code"], 502)
        self.assertNotIn("droid", neutral["message"].lower())
        self.assertEqual(neutral["message"], "cli-exec reported an error")
        self.assertEqual(with_err, body)

    def test_first_token_timeout_message_neutral_type_unchanged(self):
        out = {"state": "first_token_timeout"}
        legacy = server.Handler._error_body(out)
        self.assertIn("droid exec gave no event", legacy["message"])
        with mock.patch.dict(os.environ, {NEUTRAL_FLAG: "true"}):
            neutral = server.Handler._error_body(out)
        self.assertEqual((neutral["type"], neutral["code"]), ("first_token_timeout", 504))
        self.assertIn("cli-exec gave no event", neutral["message"])
        self.assertNotIn("droid", neutral["message"].lower())

    def test_other_error_types_unchanged_under_flag(self):
        states = (
            "timeout",
            "idle_timeout",
            "queue_timeout",
            "launcher_unavailable",
            "client_gone",
            "pump_error",
        )
        legacy = {st: server.Handler._error_body({"state": st}) for st in states}
        with mock.patch.dict(os.environ, {NEUTRAL_FLAG: "true"}):
            for st in states:
                with self.subTest(state=st):
                    neutral = server.Handler._error_body({"state": st})
                    self.assertEqual(neutral["type"], legacy[st]["type"])
                    self.assertEqual(neutral["code"], legacy[st]["code"])


class TestHealthContractUnderFlags(_FlagEnvMixin, BridgeCase):
    def setUp(self):
        super().setUp()
        self.isolate_flags()

    def _health(self, path="/health"):
        status, body = self._get(path, auth=False)
        self.assertEqual(status, 200)
        return body

    def test_health_has_exactly_seven_keys_by_default(self):
        body = self._health()
        self.assertEqual(set(body), HEALTH_KEYS)
        self.assertEqual(len(body), 7)
        self.assertEqual(body["transport"], "droid-exec")
        self.assertIs(body["tool_emulation"], True)

    def test_health_unchanged_under_every_flag_combination(self):
        base_keys = set(self._health())
        combos = [{flag: "true"} for flag in BEHAVIOR_FLAGS]
        combos.append({flag: "true" for flag in BEHAVIOR_FLAGS})
        combos.append({flag: "false" for flag in BEHAVIOR_FLAGS})
        for combo in combos:
            for path in ("/health", "/v1/health"):
                with self.subTest(flags=sorted(combo), path=path), mock.patch.dict(os.environ, combo):
                    body = self._health(path)
                    self.assertEqual(set(body), base_keys)
                    self.assertEqual(len(body), 7)
                    self.assertEqual(body["transport"], "droid-exec")

    def test_health_has_no_liveness_or_runtime_config_leak(self):
        with mock.patch.dict(os.environ, {flag: "true" for flag in BEHAVIOR_FLAGS}):
            text = json.dumps(self._health())
        for needle in ("liveness", "cli-exec", "cli-agent-bridge", "BRIDGE_CLI_", "BRIDGE_NONSTREAM_"):
            self.assertNotIn(needle, text)


class TestCompletionIdPrefixEndToEnd(_FlagEnvMixin, RpcCase):
    def setUp(self):
        super().setUp()
        self.isolate_flags()

    def test_completion_id_prefix_default_and_neutral(self):
        status, data = self.conv("c-prefix-default").ask("hello")
        self.assertEqual(status, 200)
        self.assertTrue(data["id"].startswith("chatcmpl-droid-"), data["id"])
        with mock.patch.dict(os.environ, {NEUTRAL_FLAG: "true"}):
            status, data = self.conv("c-prefix-neutral").ask("hello")
        self.assertEqual(status, 200)
        self.assertTrue(data["id"].startswith("chatcmpl-cli-"), data["id"])
        self.assertNotIn("droid", data["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Тесты окружения потомка `droid exec`: что доезжает, что вырезается.

Проверяется контракт `_launch_env()`: FACTORY_API_KEY (headless-вход Droid)
сохраняется, авторизационные ключи моста (BRIDGE_KEY, DROID_DSH_BRIDGE_KEY, любые
`*_BRIDGE_KEY` и `BRIDGE_*KEY*`) вырезаются (ADR 0015, BLOCKER-SAFETY B1).
Сеть и droid не вызываются; значения ключей в тесте фиктивные.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.backend_adapter import is_bridge_secret_name, strip_bridge_secrets  # noqa: E402

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
            "PATH": os.environ.get("PATH", "/usr/bin"),
        }
        with mock.patch.dict(os.environ, {**secrets, **ordinary}):
            env = server._launch_env()
        for name in secrets:
            self.assertNotIn(name, env, name)
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

    def test_masking_covers_short_factory_key(self):
        masked = server._mask_secrets("auth: " + FAKE_FACTORY_KEY)
        self.assertNotIn(FAKE_FACTORY_KEY, masked)
        self.assertIn("***", masked)

    def test_masking_leaves_ordinary_text_intact(self):
        plain = "no secrets here at all"
        self.assertEqual(server._mask_secrets(plain), plain)


if __name__ == "__main__":
    unittest.main(verbosity=2)
